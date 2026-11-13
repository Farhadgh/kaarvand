"""Wallet top-up: create the payment, verify the gateway callback, credit once.

The customer leaves the app for the gateway, so the callback is the only place
that can turn money into balance. It is therefore:

* **idempotent** — the payment row is locked and an already paid row returns
  early (Zarinpal itself answers ``101`` for a second verify);
* **fail closed** — only ``Status=OK`` *and* a verified answer credit the wallet;
  anything else leaves the row as ``canceled``/``failed`` for the admin view;
* **tenant safe** — the lookup runs with ``app.bypass_rls`` because no token is
  present yet, then the session is bound to the payment's organization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.registry import get_gateway
from app.billing.wallet import TOMAN, credit, get_or_create_wallet
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.db.models import Payment, User, Wallet
from app.db.session import set_bypass_rls, set_tenant

log = get_logger("openbot.billing.topup")

STATUS_PENDING = "pending"
STATUS_PAID = "paid"
STATUS_CANCELED = "canceled"
STATUS_FAILED = "failed"


def to_irr(amount_toman: int) -> int:
    return int(amount_toman) * TOMAN


def to_toman(amount_irr: int) -> int:
    return int(amount_irr) // TOMAN


def payment_payload(payment: Payment) -> dict[str, Any]:
    """Shape one payment for the API (amounts in both units)."""
    return {
        "id": payment.id,
        "amount_irr": int(payment.amount_irr),
        "amount_toman": to_toman(payment.amount_irr),
        "status": payment.status,
        "gateway": payment.gateway,
        "authority": payment.authority,
        "reference": payment.reference,
        "description_fa": payment.description_fa,
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
    }


def return_url(payment: Payment, settings: Settings) -> str:
    """Deep link (or web page) the customer lands on after the gateway."""
    base = settings.payment_return_url or "kaarvand://wallet"
    query = urlencode(
        {
            "status": payment.status,
            "payment": str(payment.id),
            "ref": payment.reference or "",
        }
    )
    return f"{base}{'&' if '?' in base else '?'}{query}"


async def start_topup(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    amount_irr: int,
    callback_url: str,
    description_fa: str | None = None,
) -> Payment:
    """Create a pending payment and ask the gateway for a redirect URL."""
    amount_irr = int(amount_irr)
    if amount_irr < settings.min_topup_irr:
        raise AppError(
            code="wallet.amount_below_min",
            status_code=422,
            params={
                "min_irr": settings.min_topup_irr,
                "min_toman": to_toman(settings.min_topup_irr),
            },
        )

    wallet = await get_or_create_wallet(db, org_id=user.org_id, user_id=user.id)
    if not wallet.is_enabled:
        raise AppError(code="wallet.disabled", status_code=409)

    gateway = get_gateway(settings)
    payment = Payment(
        org_id=user.org_id,
        user_id=user.id,
        wallet_id=wallet.id,
        gateway=gateway.name,  # type: ignore[attr-defined]
        amount_irr=amount_irr,
        status=STATUS_PENDING,
        description_fa=description_fa or f"شارژ کیف پول ({to_toman(amount_irr)} تومان)",
        meta={"callback_url": callback_url},
    )
    db.add(payment)
    await db.flush()

    init = await gateway.create_payment(  # type: ignore[attr-defined]
        amount_irr=amount_irr,
        order_id=str(payment.id),
        callback_url=callback_url,
        description_fa=payment.description_fa or "",
    )
    payment.authority = init.token
    payment.meta = {**(payment.meta or {}), "redirect_url": init.redirect_url}
    await db.flush()

    log.info(
        "topup.started",
        payment_id=str(payment.id),
        user_id=str(user.id),
        amount_irr=amount_irr,
        gateway=payment.gateway,
    )
    return payment


async def apply_callback(
    db: AsyncSession,
    *,
    authority: str,
    status: str | None,
    settings: Settings,
) -> Payment:
    """Resolve the gateway redirect: verify, credit once, return the payment."""
    authority = (authority or "").strip()
    if not authority:
        raise AppError(code="payment.missing_authority", status_code=422)

    await set_bypass_rls(db, True)
    payment = (
        await db.execute(
            select(Payment).where(Payment.authority == authority).with_for_update()
        )
    ).scalar_one_or_none()

    if payment is None:
        log.warning("topup.callback_unknown", authority=authority)
        raise NotFoundError(code="payment.not_found")

    if payment.status == STATUS_PAID:
        # a retried callback (or the customer refreshing the page)
        return payment

    # from here on we are a normal tenant session again
    await set_bypass_rls(db, False)
    await set_tenant(db, payment.org_id)

    meta: dict[str, Any] = dict(payment.meta or {})
    meta["callback_status"] = (status or "").upper()

    if (status or "").strip().upper() != "OK":
        payment.status = STATUS_CANCELED
        payment.meta = meta
        await db.flush()
        log.info("topup.canceled", payment_id=str(payment.id), status=status)
        return payment

    gateway = get_gateway(settings)
    result = await gateway.verify_payment(  # type: ignore[attr-defined]
        token=authority, amount_irr=int(payment.amount_irr)
    )

    if not result.paid:
        payment.status = STATUS_FAILED
        payment.meta = {**meta, "verify": result.raw}
        await db.flush()
        log.info("topup.verify_failed", payment_id=str(payment.id), verify=result.raw)
        return payment

    if result.amount_irr and int(result.amount_irr) != int(payment.amount_irr):
        payment.status = STATUS_FAILED
        payment.meta = {**meta, "verify": result.raw, "amount_mismatch": result.amount_irr}
        await db.flush()
        log.warning(
            "topup.amount_mismatch",
            payment_id=str(payment.id),
            expected=payment.amount_irr,
            got=result.amount_irr,
        )
        raise AppError(
            code="payment.amount_mismatch",
            status_code=409,
            params={"expected_irr": int(payment.amount_irr), "got_irr": int(result.amount_irr)},
        )

    wallet = await db.get(Wallet, payment.wallet_id)
    if wallet is None:
        raise NotFoundError(code="wallet.not_found")

    await credit(
        db,
        wallet,
        amount_irr=int(payment.amount_irr),
        kind="topup",
        ref=result.reference or authority,
        note=f"شارژ کیف پول ({to_toman(payment.amount_irr)} تومان)",
    )
    payment.status = STATUS_PAID
    payment.reference = result.reference or None
    payment.paid_at = datetime.now(UTC)
    payment.meta = {**meta, "verify_code": result.raw.get("data", {}).get("code")}
    await db.flush()

    log.info(
        "topup.paid",
        payment_id=str(payment.id),
        user_id=str(payment.user_id),
        amount_irr=int(payment.amount_irr),
        reference=payment.reference,
    )
    return payment
