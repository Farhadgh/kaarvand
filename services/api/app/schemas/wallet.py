"""Wallet schemas (amounts in IRR, the client renders Toman)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WalletOut(BaseModel):
    balance_irr: int
    balance_toman: int
    currency: str
    is_enabled: bool
    usd_irr: int
    markup_percent: int
    min_topup_irr: int = 0
    min_topup_toman: int = 0
    topup_enabled: bool = False


class WalletTransactionOut(ORMModel):
    id: uuid.UUID
    amount_irr: int
    amount_toman: int = 0
    kind: str
    ref: str | None = None
    note: str | None = None
    created_at: Any = None


class TopupIn(BaseModel):
    """The customer thinks in Toman; the API converts once, here."""

    amount_toman: int = Field(ge=1_000, le=500_000_000)
    description_fa: str | None = Field(default=None, max_length=200)


class TopupOut(BaseModel):
    payment_id: uuid.UUID
    amount_irr: int
    amount_toman: int
    gateway: str
    authority: str | None = None
    redirect_url: str
    status: str


class PaymentOut(ORMModel):
    id: uuid.UUID
    amount_irr: int
    amount_toman: int
    status: str
    gateway: str
    authority: str | None = None
    reference: str | None = None
    description_fa: str | None = None
    paid_at: Any = None
    created_at: Any = None


class AdminPaymentOut(PaymentOut):
    user_id: uuid.UUID
    user_phone: str | None = None
    user_name: str | None = None


class PaymentSummaryOut(BaseModel):
    """Admin accounting: what came in, what is still open."""

    days: int
    paid_count: int
    paid_irr: int
    paid_toman: int
    pending_count: int
    failed_count: int
    canceled_count: int
    today_paid_irr: int
    today_paid_toman: int

