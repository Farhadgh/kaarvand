"""Meta / capability discovery schemas."""

from __future__ import annotations

from pydantic import BaseModel


class MetaOut(BaseModel):
    """Everything the Persian web client needs before rendering anything."""

    app_name: str
    version: str
    env: str
    locale: str
    timezone: str
    calendar: str
    currency: str
    digits: str
    free_mode: bool
    billing_enabled: bool
    payment_gateway: str
    payment_gateway_enabled: bool
    fx_usd_irr: int
    api_prefix: str


class HealthOut(BaseModel):
    status: str
    db: str
    version: str
