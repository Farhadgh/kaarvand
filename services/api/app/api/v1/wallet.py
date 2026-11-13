"""The customer's wallet: balance, statement and Zarinpal top-up."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.fx import current_fx_rate
from app.billing.registry import get_gateway
from app.billing.topup import (
    apply_callback,
    payment_payload,
    return_url,
    start_topup,
    to_irr,
    to_toman,
)
from app.billing.wallet import TOMAN, get_or_create_wallet, recent_transactions
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db, require_member
from app.db.models import Payment, User
from app.schemas.wallet import (
    PaymentOut,
    TopupIn,
    TopupOut,
    WalletOut,
    WalletTransactionOut,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletOut)
async def read_wallet(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_member),
    settings: Settings = Depends(get_settings),
) -> WalletOut:
    wallet = await get_or_create_wallet(db, org_id=user.org_id, user_id=user.id)
    usd_irr = await current_fx_rate(db, settings)
    balance = int(wallet.balance_irr)
    gateway = get_gateway(settings)
    return WalletOut(
        balance_irr=balance,
        balance_toman=balance // TOMAN,
        currency=wallet.currency,
        is_enabled=wallet.is_enabled,
        usd_irr=usd_irr,
        markup_percent=settings.platform_markup_percent,
        min_topup_irr=settings.min_topup_irr,
        min_topup_toman=to_toman(settings.min_topup_irr),
        topup_enabled=bool(getattr(gateway, "enabled", False)),
    )


@router.get("/transactions", response_model=list[WalletTransactionOut])
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WalletTransactionOut]:
    wallet = await get_or_create_wallet(db, org_id=user.org_id, user_id=user.id)
    rows = await recent_transactions(db, wallet.id, limit=limit)
    return [
        WalletTransactionOut(
            id=row.id,
            amount_irr=int(row.amount_irr),
            amount_toman=int(row.amount_irr) // TOMAN,
            kind=row.kind,
            ref=row.ref,
            note=row.note,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/topup", response_model=TopupOut, status_code=status.HTTP_201_CREATED)
async def create_topup(
    payload: TopupIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_member),
    settings: Settings = Depends(get_settings),
) -> TopupOut:
    """Open a Zarinpal payment and hand the client a redirect URL."""
    callback_url = settings.payment_callback or (
        f"{str(request.base_url).rstrip('/')}{settings.api_prefix}/wallet/topup/callback"
    )
    payment = await start_topup(
        db,
        user=user,
        settings=settings,
        amount_irr=to_irr(payload.amount_toman),
        callback_url=callback_url,
        description_fa=payload.description_fa,
    )
    redirect_url = str((payment.meta or {}).get("redirect_url") or "")
    return TopupOut(
        payment_id=payment.id,
        amount_irr=int(payment.amount_irr),
        amount_toman=to_toman(payment.amount_irr),
        gateway=payment.gateway,
        authority=payment.authority,
        redirect_url=redirect_url,
        status=payment.status,
    )


@router.get("/topup/callback", include_in_schema=False)
async def topup_callback(
    authority: str = Query(default="", alias="Authority"),
    status_param: str = Query(default="", alias="Status"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Public redirect target of the gateway; always sends the app back home."""
    payment = await apply_callback(
        db, authority=authority, status=status_param, settings=settings
    )
    return RedirectResponse(
        url=return_url(payment, settings), status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/payments", response_model=list[PaymentOut])
async def list_my_payments(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_member),
) -> list[PaymentOut]:
    rows = (
        await db.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return [PaymentOut(**payment_payload(row)) for row in rows]

