"""Account link schemas (the customer's own social accounts)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LinkCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=32)
    # the customer's own laptop; omitted = any online device of the account
    device_id: uuid.UUID | None = None


class LinkToolOut(BaseModel):
    name: str
    title_fa: str
    description_fa: str
    input_schema: dict[str, Any]


class LinkProviderOut(BaseModel):
    """One card in «حساب‌ها»: what it is and what the agent may do with it."""

    slug: str
    title_fa: str
    auth_kind: str
    site_url: str
    login_hint_fa: str
    notes_fa: str = ""
    rate_limit_per_hour: int
    available: bool = True
    tools: list[LinkToolOut] = Field(default_factory=list)


class LinkOut(ORMModel):
    id: uuid.UUID
    provider: str
    auth_kind: str
    transport: str
    status: str
    display_name: str | None = None
    avatar_url: str | None = None
    phone_hint: str | None = None
    external_account_id: str | None = None
    device_id: uuid.UUID | None = None
    rate_limit_per_hour: int
    last_error: str | None = None
    last_seen_at: Any = None
    created_at: Any = None
    # filled by the API, not by the row
    provider_title_fa: str = ""
    device_online: bool = False
    tool_slugs: list[str] = Field(default_factory=list)
    login_opened: bool = False


class LinkProbeOut(BaseModel):
    ok: bool = True
    logged_in: bool
    status: str
    display_name: str | None = None
    external_account_id: str | None = None
    hint_fa: str | None = None
    tools: list[str] = Field(default_factory=list)
    # a base64 PNG of the page, so the customer can see what the bridge sees
    screenshot: str | None = None
    detail: str | None = None


class LinkSyncOut(BaseModel):
    tools: list[str]
    count: int


class LinkOpenOut(BaseModel):
    ok: bool = True
    window: str


class LinkAssetOut(ORMModel):
    id: uuid.UUID
    link_id: uuid.UUID
    kind: str
    external_id: str | None = None
    name: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool
