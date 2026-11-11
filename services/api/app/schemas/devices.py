"""Device (connector) schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class DeviceOut(ORMModel):
    id: uuid.UUID
    name: str
    os: str | None = None
    version: str | None = None
    status: str
    allowed_paths: list[str]
    is_active: bool
    last_seen_at: Any = None


class DeviceWithCodeOut(DeviceOut):
    pairing_code: str
    pairing_expires_at: Any


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    allowed_paths: list[str] | None = None
    is_active: bool | None = None


class PairIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)
    pubkey: str = Field(min_length=8, max_length=2000)
    os: str | None = Field(default=None, max_length=32)
    version: str | None = Field(default=None, max_length=32)


class PairOut(BaseModel):
    device_id: uuid.UUID
    device_token: str
    ws_url: str


class DeviceOpsOut(BaseModel):
    device_id: uuid.UUID
    online: bool
    ops: list[str]
    manifest: dict[str, Any]
