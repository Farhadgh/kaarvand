"""Inbound channels: where messages come *in* (Telegram / WhatsApp webhooks).

A channel binds a public webhook URL to one agent. Every accepted message
creates a normal `runs` row (`trigger="webhook"`), so approvals, budgets, cost
and the tool policy keep working exactly as for a manual run.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey

INBOUND_PROVIDERS = ("telegram", "whatsapp")
REPLY_MODES = ("off", "auto")


class InboundChannel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "inbound_channels"
    __table_args__ = (
        # globally unique: the public webhook only knows the slug, not the tenant
        UniqueConstraint("slug", name="uq_inbound_channels_slug"),
        Index("ix_inbound_channels_org", "org_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    # the installed app tool used to answer (telegram.<agent8> ...); optional
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tools.id", ondelete="SET NULL"), nullable=True
    )
    reply_mode: Mapped[str] = mapped_column(String(8), default="off", nullable=False)

    # telegram: X-Telegram-Bot-Api-Secret-Token; whatsapp: app secret (HMAC-SHA256)
    verify_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # whatsapp only: hub.verify_token for the GET handshake
    verify_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    events_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class InboundEvent(UUIDPrimaryKey, Base):
    """One accepted provider delivery. The unique key makes retries idempotent."""

    __tablename__ = "inbound_events"
    __table_args__ = (
        UniqueConstraint("channel_id", "external_id", name="uq_inbound_events_external"),
        Index("ix_inbound_events_channel_time", "channel_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("inbound_channels.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="accepted", nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    from_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
