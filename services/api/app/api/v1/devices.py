"""Device (connector) REST endpoints: create, pair, list, tune."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.hub import hub
from app.connector.pairing import (
    codes_match,
    is_expired,
    issue_device_token,
    new_pairing_code,
    pairing_expiry,
)
from app.core.deps import get_current_user, get_db, require_roles
from app.core.errors import AppError, NotFoundError
from app.db.models import Device, User
from app.db.session import session_scope
from app.schemas.devices import (
    DeviceCreate,
    DeviceOpsOut,
    DeviceOut,
    DeviceUpdate,
    DeviceWithCodeOut,
    PairIn,
    PairOut,
)

router = APIRouter(tags=["devices"])
editor = require_roles("owner", "admin")


async def _get_device(db: AsyncSession, user: User, device_id: uuid.UUID) -> Device:
    device = (
        await db.execute(
            select(Device).where(Device.id == device_id, Device.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if device is None:
        raise NotFoundError(code="device.not_found")
    return device


def _with_code(device: Device) -> DeviceWithCodeOut:
    out = DeviceWithCodeOut.model_validate(device)
    out.pairing_code = device.pairing_code or ""
    out.pairing_expires_at = device.pairing_expires_at
    return out


@router.post("/devices", response_model=DeviceWithCodeOut, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> DeviceWithCodeOut:
    device = Device(
        org_id=user.org_id,
        name=payload.name,
        status="pending",
        pairing_code=new_pairing_code(),
        pairing_expires_at=pairing_expiry(),
        allowed_paths=[],
    )
    db.add(device)
    await db.flush()
    return _with_code(device)


@router.post("/devices/pair", response_model=PairOut)
async def pair_device(payload: PairIn, request: Request) -> PairOut:
    """Called by the connector itself: pairing code + public key -> device token."""
    async with session_scope(bypass_rls=True) as db:
        device = (
            await db.execute(
                select(Device).where(Device.pairing_code == payload.code.strip().upper())
            )
        ).scalar_one_or_none()
        if device is None or not codes_match(device.pairing_code, payload.code):
            raise AppError(code="device.invalid_code", status_code=401)
        if is_expired(device.pairing_expires_at):
            raise AppError(code="device.code_expired", status_code=410)
        if not device.is_active:
            raise AppError(code="device.disabled", status_code=403)

        device.pubkey = payload.pubkey
        device.os = payload.os
        device.version = payload.version
        device.status = "paired"
        device.pairing_code = None
        device.pairing_expires_at = None
        await db.flush()

        token = issue_device_token(device_id=device.id, org_id=device.org_id)
        device_id = device.id

    base = str(request.base_url).rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return PairOut(
        device_id=device_id,
        device_token=token,
        ws_url=f"{ws_base}/v1/ws/connector",
    )


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeviceOut]:
    rows = (
        await db.execute(
            select(Device).where(Device.org_id == user.org_id).order_by(Device.created_at)
        )
    ).scalars().all()
    return [DeviceOut.model_validate(row) for row in rows]


@router.get("/devices/{device_id}", response_model=DeviceOut)
async def read_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceOut:
    return DeviceOut.model_validate(await _get_device(db, user, device_id))


@router.get("/devices/{device_id}/ops", response_model=DeviceOpsOut)
async def device_ops(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceOpsOut:
    device = await _get_device(db, user, device_id)
    session = hub.get(device.id)
    manifest = dict(session.manifest) if session else {}
    return DeviceOpsOut(
        device_id=device.id,
        online=session is not None,
        ops=list(manifest.get("ops") or []),
        manifest=manifest,
    )


@router.patch("/devices/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: uuid.UUID,
    payload: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> DeviceOut:
    device = await _get_device(db, user, device_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    await db.flush()
    return DeviceOut.model_validate(device)


@router.post("/devices/{device_id}/rotate-code", response_model=DeviceWithCodeOut)
async def rotate_pairing_code(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> DeviceWithCodeOut:
    device = await _get_device(db, user, device_id)
    device.pairing_code = new_pairing_code()
    device.pairing_expires_at = pairing_expiry()
    device.status = "pending"
    await db.flush()
    return _with_code(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(editor),
) -> Response:
    device = await _get_device(db, user, device_id)
    hub.unregister(device.id)
    await db.delete(device)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _unused(_: Any) -> None:  # pragma: no cover
    return None
