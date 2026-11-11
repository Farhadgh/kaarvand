"""WebSocket channel for desktop connectors (outbound dial, no inbound port)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.connector.hub import DeviceSession, hub
from app.connector.pairing import read_device_token
from app.core.logging import get_logger
from app.db.models import Device
from app.db.session import session_scope

router = APIRouter(tags=["connector"])
log = get_logger("openbot.connector.ws")


async def _touch(
    org_id: uuid.UUID,
    device_id: uuid.UUID,
    *,
    status: str,
    os_name: str | None = None,
    version: str | None = None,
) -> None:
    async with session_scope(org_id=org_id) as db:
        device = await db.get(Device, device_id)
        if device is None:
            return
        device.status = status
        device.last_seen_at = datetime.now(UTC)
        if os_name:
            device.os = os_name
        if version:
            device.version = version


async def _device_active(org_id: uuid.UUID, device_id: uuid.UUID) -> bool:
    async with session_scope(org_id=org_id) as db:
        device = (
            await db.execute(select(Device).where(Device.id == device_id))
        ).scalar_one_or_none()
        return bool(device and device.is_active)


@router.websocket("/ws/connector")
async def connector_socket(websocket: WebSocket, token: str = Query(default="")) -> None:
    try:
        device_id, org_id = read_device_token(token)
    except Exception:  # noqa: BLE001 - any auth problem closes the socket
        await websocket.close(code=4401)
        return

    if not await _device_active(org_id, device_id):
        await websocket.close(code=4403)
        return

    await websocket.accept()

    async def send(payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    session = DeviceSession(device_id=device_id, org_id=org_id, send=send)
    hub.register(session)
    await _touch(org_id, device_id, status="online")

    try:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type")

            if kind == "hello":
                session.manifest = message.get("manifest") or {}
                session.os = message.get("os")
                session.version = message.get("version")
                session.name = str(message.get("name") or "")
                await _touch(
                    org_id,
                    device_id,
                    status="online",
                    os_name=session.os,
                    version=session.version,
                )
                await send(
                    {
                        "type": "hello.ack",
                        "device_id": str(device_id),
                        "server_time": datetime.now(UTC).isoformat(),
                    }
                )
            elif kind in ("script.result", "apps.result"):
                hub.resolve(str(message.get("call_id") or ""), message)
            elif kind == "script.progress":
                log.info(
                    "connector.progress",
                    device_id=str(device_id),
                    step=message.get("step"),
                    op=message.get("op"),
                )
            elif kind == "ping":
                await send({"type": "pong"})
    except WebSocketDisconnect:
        log.info("connector.socket_closed", device_id=str(device_id))
    finally:
        hub.unregister(device_id)
        await _touch(org_id, device_id, status="offline")
