"""Noop gateway used while the product runs in free mode."""

from __future__ import annotations

from typing import Any

from app.billing.gateway import PaymentInit, PaymentResult, RefundResult, WebhookEvent
from app.core.errors import BillingDisabledError


class NoopGateway:
    name = "noop"
    enabled = False

    async def create_payment(
        self,
        *,
        amount_irr: int,
        order_id: str,
        callback_url: str,
        description_fa: str,
    ) -> PaymentInit:
        raise BillingDisabledError()

    async def verify_payment(self, *, token: str, amount_irr: int) -> PaymentResult:
        raise BillingDisabledError()

    async def refund(self, *, reference: str, amount_irr: int) -> RefundResult:
        raise BillingDisabledError()

    def parse_webhook(self, raw: bytes, headers: dict[str, str]) -> WebhookEvent:
        raise BillingDisabledError()


def describe(gateway: Any) -> dict[str, Any]:
    return {"gateway": gateway.name, "enabled": bool(getattr(gateway, "enabled", False))}
