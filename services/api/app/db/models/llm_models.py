"""LLM models, price history and capability inference rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey


class Model(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_id", name="uq_models_provider_external"),
        Index("ix_models_enabled_tools", "is_enabled", "supports_tools"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name_fa: Mapped[str | None] = mapped_column(String(200), nullable=True)
    family: Mapped[str | None] = mapped_column(String(80), nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modalities: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_stream: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    input_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    cached_input_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    image_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    price_unit: Mapped[str] = mapped_column(String(16), default="per_token", nullable=False)
    price_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    price_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    markup_percent: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    provider: Mapped["Provider"] = relationship(back_populates="models")  # noqa: F821, UP037


class PriceHistory(UUIDPrimaryKey, Base):
    """Append only: every invoice must be reproducible with the price of that moment."""

    __tablename__ = "price_history"
    __table_args__ = (Index("ix_price_history_model_time", "model_id", "effective_from"),)

    model_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("models.id", ondelete="CASCADE"), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    output_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    cached_input_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    image_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 10), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CapabilityRule(UUIDPrimaryKey, TimestampMixin, Base):
    """Regex rules that infer capabilities from a model id during sync."""

    __tablename__ = "capability_rules"

    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    flags: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
