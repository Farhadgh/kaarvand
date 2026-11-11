"""Payment gateway port.

Phase 1 ships only ``noop``. Adding Zarinpal / IDPay later means:
  1. add ``app/billing/zarinpal.py`` implementing ``PaymentGateway``
  2. register it in ``GATEWAYS``
  3. set ``APP_PAYMENT_GATEWAY=zarinpal``
No other module changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PaymentInit:
    gateway: str
    token: str
    redirect_url: str


@dataclass(frozen=True, slots=True)
class PaymentResult:
    gateway: str
    reference: str
    paid: bool
    amount_irr: int
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RefundResult:
    reference: str
    refunded: bool
    amount_irr: int


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    kind: str
    reference: str
    paid: bool
    amount_irr: int
    raw: dict[str, Any]


@runtime_checkable
class PaymentGateway(Protocol):
    name: str
    enabled: bool

    async def create_payment(
        self,
        *,
        amount_irr: int,
        order_id: str,
        callback_url: str,
        description_fa: str,
    ) -> PaymentInit: ...

    async def verify_payment(self, *, token: str, amount_irr: int) -> PaymentResult: ...

    async def refund(self, *, reference: str, amount_irr: int) -> RefundResult: ...

    def parse_webhook(self, raw: bytes, headers: dict[str, str]) -> WebhookEvent: ...
