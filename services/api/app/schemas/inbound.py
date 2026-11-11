"""Inbound webhook schemas: channels (admin) and events (read only)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

Provider = Literal["telegram", "whatsapp"]
ReplyMode = Literal["off", "auto"]


class InboundChannelCreate(BaseModel):
    name_fa: str = Field(min_length=1, max_length=160)
    provider: Provider
    agent_id: uuid.UUID
    tool_id: uuid.UUID | None = None
    reply_mode: ReplyMode = "off"
    # telegram: secret_token set via setWebhook; whatsapp: app secret (HMAC)
    verify_secret: str | None = Field(default=None, min_length=1, max_length=256)
    # whatsapp only: hub.verify_token for the GET handshake
    verify_token: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool = True


class InboundChannelUpdate(BaseModel):
    name_fa: str | None = Field(default=None, min_length=1, max_length=160)
    agent_id: uuid.UUID | None = None
    tool_id: uuid.UUID | None = None
    reply_mode: ReplyMode | None = None
    verify_secret: str | None = Field(default=None, min_length=1, max_length=256)
    verify_token: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class InboundChannelOut(ORMModel):
    id: uuid.UUID
    slug: str
    name_fa: str
    provider: str
    agent_id: uuid.UUID
    tool_id: uuid.UUID | None = None
    reply_mode: str
    is_active: bool
    last_event_at: Any = None
    events_count: int
    has_secret: bool = False
    has_verify_token: bool = False
    # paths the panel shows next to each channel
    webhook_path: str = ""
    verify_path: str = ""
    # absolute URL (built from APP_PUBLIC_BASE_URL or the request origin)
    webhook_url: str = ""
    # last delivery, so the panel does not need a second request
    last_event_status: str | None = None
    last_reply_status: str | None = None
    last_error: str | None = None


class InboundEventOut(ORMModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    provider: str
    external_id: str
    status: str
    run_id: uuid.UUID | None = None
    from_id: str | None = None
    chat_id: str | None = None
    text: str | None = None
    reply_status: str | None = None
    error: str | None = None
    created_at: Any = None


class InboundAcceptedOut(BaseModel):
    """What the provider gets back: always 200, never an internal error."""

    ok: bool = True
    status: str  # accepted | duplicate | ignored | disabled
    event_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None


class InboundTestIn(BaseModel):
    text: str = Field(default="سلام! این یک پیام آزمایشی است.", min_length=1, max_length=1000)
    chat_id: str = Field(default="test-chat", max_length=60)
    from_id: str = Field(default="test-user", max_length=60)


class InboundTestOut(BaseModel):
    """Result of the "test webhook" button: a real run, no phone required."""

    ok: bool
    status: str
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    reply_status: str | None = None
    # True when the run parked because a tool needs human approval
    needs_approval: bool = False
    text: str | None = None


class WebhookRegisterOut(BaseModel):
    ok: bool
    url: str
    detail: str | None = None
    public_base_url: bool = True  # False when we had to guess from the request
