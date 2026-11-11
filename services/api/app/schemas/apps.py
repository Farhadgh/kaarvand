"""App catalog schemas: list, detail, install, device apps."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppOut(ORMModel):
    id: uuid.UUID
    slug: str
    name_fa: str
    name_en: str | None = None
    vendor: str | None = None
    description_fa: str | None = None
    icon: str
    color: str | None = None
    category: str
    runtime: str
    tool_kind: str
    risk_level: str
    approval_policy: str
    requires_device: bool
    setup_fa: str | None = None
    docs_url: str | None = None
    sort_order: int
    # computed
    installed_tools: int = 0
    installed_agents: int = 0
    detected_devices: int = 0


class AppDetailOut(AppOut):
    input_schema: dict[str, Any]
    config_template: dict[str, Any]
    actions_template: list[dict[str, Any]]
    credentials: list[dict[str, Any]]
    detect: dict[str, Any]


class AppInstallIn(BaseModel):
    agent_id: uuid.UUID
    permission_level: str = Field(default="confirm", pattern="^(auto|confirm|deny)$")
    device_id: uuid.UUID | None = None
    # non-secret wizard fields, e.g. {"chat_id": "-100123", "phone_number_id": "123"}
    variables: dict[str, str] = Field(default_factory=dict)
    # the one encrypted credential (bot token, api key, ...)
    secret: str | None = Field(default=None, max_length=4096)
    secret_label: str | None = Field(default=None, max_length=40)
    name_fa: str | None = Field(default=None, min_length=1, max_length=200)
    # allow installing a desktop app that the connector did not detect yet
    force: bool = False
    # extra/overriding config keys (advanced)
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class AppInstallOut(BaseModel):
    tool_id: uuid.UUID
    slug: str
    agent_id: uuid.UUID
    permission_level: str
    device_id: uuid.UUID | None = None
    warnings: list[str] = Field(default_factory=list)


class DeviceAppOut(BaseModel):
    app_slug: str
    name_fa: str | None = None
    icon: str | None = None
    color: str | None = None
    version: str | None = None
    exe: str | None = None
    prog_id: str | None = None
    is_granted: bool = False
    detected_at: Any = None
    in_catalog: bool = False


class DeviceAppGrantIn(BaseModel):
    is_granted: bool = True


class AppScanOut(BaseModel):
    device_id: uuid.UUID
    online: bool
    found: int
    apps: list[DeviceAppOut]
