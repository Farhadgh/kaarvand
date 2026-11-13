"""Admin accounting for wallet top-ups (payments page of the panel)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.topup import (
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_PAID,
    STATUS_PENDING,
    apply_callback,
    payment_payload,
    to_toman,
)
from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.core.errors import AppError, NotFoundError
from app.db.models import Payment, User
from app.schemas.wallet import AdminPaymentOut, PaymentSummaryOut

router = APIRouter(prefix="/payments", tags=["payments"])
admin_only = require_admin


@router.get("", response_model=list[AdminPaymentOut])
async def list_payments(
    status_filter: str | None = Query(default=None, alias="status"),
    user_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(admin_only),
) -> list[AdminPaymentOut]:
    stmt = (
        select(Payment, User.phone, User.full_name)
        .join(User, User.id == Payment.user_id)
        .where(Payment.org_id == actor.org_id)
    )
    if status_filter:
        stmt = stmt.where(Payment.status == status_filter)
    if user_id is not None:
        stmt = stmt.where(Payment.user_id == user_id)

    rows = (
        await db.execute(stmt.order_by(Payment.created_at.desc()).limit(limit))
    ).all()
    return [
        AdminPaymentOut(
            **payment_payload(payment),
            user_id=payment.user_id,
            user_phone=phone,
            user_name=name,
        )
        for payment, phone, name in rows
    ]


@router.get("/summary", response_model=PaymentSummaryOut)
async def payment_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> PaymentSummaryOut:
    """Totals per status for the last ``days``, plus today's settled amount."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                Payment.status,
                func.count(),
                func.coalesce(func.sum(Payment.amount_irr), 0),
            )
            .where(Payment.org_id == actor.org_id, Payment.created_at >= since)
            .group_by(Payment.status)
        )
    ).all()
    by_status = {status: (int(count), int(total)) for status, count, total in rows}

    tz = ZoneInfo(settings.default_timezone)
    local_midnight = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_paid = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(Payment.amount_irr), 0)).where(
                    Payment.org_id == actor.org_id,
                    Payment.status == STATUS_PAID,
                    Payment.paid_at >= local_midnight.astimezone(UTC),
                )
            )
        ).scalar_one()
    )

    paid_count, paid_irr = by_status.get(STATUS_PAID, (0, 0))
    return PaymentSummaryOut(
        days=days,
        paid_count=paid_count,
        paid_irr=paid_irr,
        paid_toman=to_toman(paid_irr),
        pending_count=by_status.get(STATUS_PENDING, (0, 0))[0],
        failed_count=by_status.get(STATUS_FAILED, (0, 0))[0],
        canceled_count=by_status.get(STATUS_CANCELED, (0, 0))[0],
        today_paid_irr=today_paid,
        today_paid_toman=to_toman(today_paid),
    )


@router.post("/{payment_id}/verify", response_model=AdminPaymentOut)
async def verify_pending_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> AdminPaymentOut:
    """Re-verify a payment whose callback never arrived (reconciliation).

    Safe to press twice: a paid payment is returned as is, and the gateway
    answers ``101`` for an already verified transaction.
    """
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.org_id != actor.org_id:
        raise NotFoundError(code="payment.not_found")
    if not payment.authority:
        raise AppError(code="payment.missing_authority", status_code=409)

    if payment.status != STATUS_PAID:
        payment = await apply_callback(
            db, authority=payment.authority, status="OK", settings=settings
        )

    user = await db.get(User, payment.user_id)
    return AdminPaymentOut(
        **payment_payload(payment),
        user_id=payment.user_id,
        user_phone=user.phone if user else None,
        user_name=user.full_name if user else None,
    )
