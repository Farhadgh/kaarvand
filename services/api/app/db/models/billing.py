"""Billing scaffolding.

Phase 1 runs in free mode: no payment gateway, no invoices. These tables exist
so adding an Iranian gateway later is a new adapter file + a settings switch,
not a schema migration across the product.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKey


class Plan(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    price_irr: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Wallet(UUIDPrimaryKey, TimestampMixin, Base):
    """One toman wallet per user (balance is stored in IRR, shown in Toman)."""

    __tablename__ = "wallets"
    __table_args__ = (
        Index(
            "uq_wallets_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    balance_irr: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="IRR", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WalletTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (Index("ix_wallet_tx_wallet_time", "wallet_id", "created_at"),)

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    amount_irr: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Payment(UUIDPrimaryKey, TimestampMixin, Base):
    """One wallet top-up attempt at an external gateway.

    The row is created *before* the customer leaves for the gateway, so a lost
    callback can always be reconciled later. ``authority`` is the gateway side
    identifier we look the payment up with when the browser comes back;
    ``reference`` is the gateway receipt number shown to the customer.

    Statuses: ``pending`` -> ``paid`` | ``canceled`` (customer quit) | ``failed``
    (gateway refused / amount mismatch). Only ``paid`` credits the wallet, and
    only once: the callback locks the row and returns early when it is paid.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_user_time", "user_id", "created_at"),
        Index("ix_payments_status_time", "status", "created_at"),
        Index("uq_payments_gateway_authority", "gateway", "authority", unique=True),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    gateway: Mapped[str] = mapped_column(String(24), nullable=False)
    authority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_irr: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
