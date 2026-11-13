"""Zarinpal payment gateway (REST v4).

Flow (three calls, exactly as the gateway documents it):

1. ``POST {host}/pg/v4/payment/request.json`` -> ``authority``
2. redirect the customer to ``{host}/pg/StartPay/{authority}``
3. the gateway returns the browser to our ``callback_url`` with
   ``?Authority=...&Status=OK|NOK``; we then ``POST .../verify.json`` and only
   credit the wallet when the answer is ``100`` (fresh) or ``101`` (already
   verified before, so the callback was retried).

Amounts are always Rial: the wallet stores Rial and the customer reads Toman.
Set ``APP_ZARINPAL_SANDBOX=true`` to talk to the test host.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.billing.gateway import PaymentInit, PaymentResult, RefundResult, WebhookEvent
from app.core.config import Settings, get_settings
from app.core.errors import AppError, BillingDisabledError
from app.core.logging import get_logger

log = get_logger("openbot.billing.zarinpal")

# 100 = verified now, 101 = verified before (a retried callback)
OK_CODES = frozenset({100, 101})


class ZarinpalGateway:
    name = "zarinpal"

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.merchant_id = (self._settings.zarinpal_merchant_id or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.merchant_id)

    # --- internals ---------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self._settings.zarinpal_host}{path}"

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise BillingDisabledError(
                code="billing.gateway_not_configured", params={"gateway": self.name}
            )
        try:
            async with httpx.AsyncClient(timeout=self._settings.payment_timeout_seconds) as client:
                response = await client.post(
                    self._url(path),
                    json=payload,
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            log.warning("zarinpal.unreachable", path=path, error=str(exc))
            raise AppError(
                code="billing.gateway_unreachable",
                status_code=502,
                params={"gateway": self.name},
                log_message=f"zarinpal {path}: {exc}",
            ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            log.warning("zarinpal.bad_response", path=path, status=response.status_code)
            raise AppError(
                code="billing.gateway_bad_response",
                status_code=502,
                params={"gateway": self.name, "status": response.status_code},
            ) from exc

        if not isinstance(body, dict):
            raise AppError(
                code="billing.gateway_bad_response",
                status_code=502,
                params={"gateway": self.name, "status": response.status_code},
            )
        return body

    @staticmethod
    def _data(body: dict[str, Any]) -> dict[str, Any]:
        data = body.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _code(data: dict[str, Any]) -> int:
        try:
            return int(data.get("code") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _errors(body: dict[str, Any]) -> Any:
        return body.get("errors")

    # --- PaymentGateway port ----------------------------------------------

    async def create_payment(
        self,
        *,
        amount_irr: int,
        order_id: str,
        callback_url: str,
        description_fa: str,
    ) -> PaymentInit:
        body = await self._post(
            self._settings.zarinpal_request_path,
            {
                "merchant_id": self.merchant_id,
                "amount": int(amount_irr),
                "currency": "IRR",
                "callback_url": callback_url,
                "description": description_fa,
                "metadata": {"order_id": order_id},
            },
        )
        data = self._data(body)
        code = self._code(data)
        authority = str(data.get("authority") or "").strip()

        if code != 100 or not authority:
            log.warning("zarinpal.request_failed", code=code, errors=self._errors(body))
            raise AppError(
                code="billing.gateway_error",
                status_code=502,
                params={"gateway": self.name, "gateway_code": code},
            )

        redirect_url = f"{self._url(self._settings.zarinpal_start_pay_path)}/{authority}"
        return PaymentInit(gateway=self.name, token=authority, redirect_url=redirect_url)

    async def verify_payment(self, *, token: str, amount_irr: int) -> PaymentResult:
        body = await self._post(
            self._settings.zarinpal_verify_path,
            {
                "merchant_id": self.merchant_id,
                "amount": int(amount_irr),
                "authority": token,
            },
        )
        data = self._data(body)
        code = self._code(data)
        paid = code in OK_CODES
        reference = str(data.get("ref_id") or "").strip()

        if not paid:
            log.info("zarinpal.verify_not_paid", code=code, errors=self._errors(body))

        return PaymentResult(
            gateway=self.name,
            reference=reference,
            paid=paid,
            amount_irr=int(amount_irr),
            raw=body,
        )

    async def refund(self, *, reference: str, amount_irr: int) -> RefundResult:
        raise AppError(
            code="billing.refund_unsupported",
            status_code=501,
            params={"gateway": self.name},
        )

    def parse_webhook(self, raw: bytes, headers: dict[str, str]) -> WebhookEvent:
        """Zarinpal calls back with a GET redirect, handled by the wallet router."""
        raise AppError(
            code="billing.webhook_unsupported",
            status_code=501,
            params={"gateway": self.name},
        )
