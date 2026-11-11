"""Settings schemas: organization, current user, exchange rate."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class OrgOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    calendar: str
    currency: str
    digits: str
    tax_rate: Decimal
    invoice_prefix: str
    monthly_budget_irr: int | None


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    calendar: Literal["jalali", "gregorian"] | None = None
    currency: str | None = Field(default=None, max_length=8)
    digits: Literal["fa", "en"] | None = None
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    invoice_prefix: str | None = Field(default=None, max_length=20)
    monthly_budget_irr: int | None = Field(default=None, ge=0)


class MeOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    locale: str
    digits_pref: str


class MeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    locale: str | None = Field(default=None, max_length=8)
    digits_pref: Literal["fa", "en"] | None = None


class FxIn(BaseModel):
    usd_irr: int = Field(ge=0, le=10_000_000_000)


class FxOut(BaseModel):
    usd_irr: int
    source: str = "manual"


class SettingsOut(BaseModel):
    org: OrgOut
    me: MeOut
    fx: FxOut
    free_mode: bool
    billing_enabled: bool
    payment_gateway: str
    version: str
    locale: str
    calendar: str
    digits: str
    timezone: str
