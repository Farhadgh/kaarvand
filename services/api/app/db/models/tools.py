"""Tool registry: http (declarative), mcp, connector (action script), builtin."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey

TOOL_KINDS = ("builtin", "http", "mcp", "connector")
RISK_LEVELS = ("low", "medium", "high")
APPROVAL_POLICIES = ("auto", "confirm", "deny")
TOOL_CATEGORIES = ("general", "social", "office", "media", "finance", "phone", "web", "dev")


class Tool(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_tools_org_slug"),
        Index("ix_tools_kind_enabled", "kind", "is_enabled"),
    )

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="http", nullable=False)

    # JSON Schema -> converted to an LLM tool schema at runtime
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # credential for http tools (bearer token, api key, ...) - never in plaintext
    secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    secret_label: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # kind=http: method/url/headers/auth/body_template/response_map
    # kind=connector: actions[] (declarative step list executed on the device)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    risk_level: Mapped[str] = mapped_column(String(8), default="low", nullable=False)
    approval_policy: Mapped[str] = mapped_column(String(8), default="auto", nullable=False)
    category: Mapped[str] = mapped_column(String(20), default="general", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class McpServer(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "mcp_servers"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    transport: Mapped[str] = mapped_column(String(16), default="http", nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    tools_cache: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Device(UUIDPrimaryKey, TimestampMixin, Base):
    """A machine where the connector runs (Excel, accounting app, softphone...)."""

    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_org_status", "org_id", "status"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    os: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pubkey: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="offline", nullable=False)
    pairing_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    pairing_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    allowed_paths: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DeviceTool(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "device_tools"
    __table_args__ = (UniqueConstraint("device_id", "tool_slug", name="uq_device_tools_slug"),)

    device_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    tool_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
