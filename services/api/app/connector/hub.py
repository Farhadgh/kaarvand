"""In-process registry of connected desktop connectors.

One channel per device: the connector dials out (no inbound port, no static IP),
authenticates with a device token and then executes action scripts we push.

Note: this registry is per worker process. Running several API workers needs a
shared bus (Postgres LISTEN/NOTIFY or Redis) - documented in docs/limitations.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.errors import AppError
from app.core.logging import get_logger

log = get_logger("openbot.connector")

Sender = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class DeviceSession:
    device_id: uuid.UUID
    org_id: uuid.UUID
    send: Sender
    name: str = ""
    os: str | None = None
    version: str | None = None
    manifest: dict[str, Any] = field(default_factory=dict)
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ConnectorHub:
    def __init__(self) -> None:
        self._sessions: dict[uuid.UUID, DeviceSession] = {}
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._owners: dict[str, uuid.UUID] = {}

    # --- registry ---------------------------------------------------------
    def register(self, session: DeviceSession) -> None:
        self._sessions[session.device_id] = session
        log.info(
            "connector.connected",
            device_id=str(session.device_id),
            org_id=str(session.org_id),
        )

    def unregister(self, device_id: uuid.UUID) -> None:
        self._sessions.pop(device_id, None)
        for call_id, owner in list(self._owners.items()):
            if owner != device_id:
                continue
            future = self._pending.pop(call_id, None)
            if future is not None and not future.done():
                future.set_exception(
                    AppError(code="tool.device_disconnected", status_code=409)
                )
            self._owners.pop(call_id, None)
        log.info("connector.disconnected", device_id=str(device_id))

    def get(self, device_id: uuid.UUID) -> DeviceSession | None:
        return self._sessions.get(device_id)

    def online_devices(self, org_id: uuid.UUID) -> list[DeviceSession]:
        return [
            session for session in self._sessions.values() if session.org_id == org_id
        ]

    def pick(self, org_id: uuid.UUID, device_id: uuid.UUID | None = None) -> DeviceSession | None:
        if device_id is not None:
            session = self._sessions.get(device_id)
            return session if session and session.org_id == org_id else None
        devices = self.online_devices(org_id)
        return devices[0] if devices else None

    # --- request / response ----------------------------------------------
    async def call(
        self,
        *,
        session: DeviceSession,
        message: dict[str, Any],
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        call_id = uuid.uuid4().hex
        payload = {**message, "call_id": call_id}
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[call_id] = future
        self._owners[call_id] = session.device_id

        try:
            await session.send(payload)
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            raise AppError(
                code="tool.device_timeout",
                status_code=504,
                params={"device_id": str(session.device_id), "timeout": timeout},
            ) from exc
        finally:
            self._pending.pop(call_id, None)
            self._owners.pop(call_id, None)

    def resolve(self, call_id: str, payload: dict[str, Any]) -> bool:
        future = self._pending.get(call_id)
        if future is None or future.done():
            return False
        future.set_result(payload)
        return True


hub = ConnectorHub()
