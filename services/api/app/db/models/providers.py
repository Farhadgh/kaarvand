"""Dynamic provider registry (adapter catalog + tenant providers)."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey


class ProviderAdapter(UUIDPrimaryKey, TimestampMixin, Base):
    """Catalog of supported adapter kinds (openai, anthropic, declarative, ...)."""

    __tablename__ = "provider_adapters"

    kind: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    spec_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Provider(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "providers"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_providers_org_slug"),
        Index("ix_providers_enabled_priority", "is_enabled", "priority"),
    )

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(20), default="bearer", nullable=False)
    credentials_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    extra_headers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    # declarative adapter (kind == "declarative"): no code needed for new protocols
    chat_spec: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_map: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    models_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    prices_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    health_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    models: Mapped[list["Model"]] = relationship(  # noqa: F821, UP037
        back_populates="provider", cascade="all, delete-orphan"
    )
