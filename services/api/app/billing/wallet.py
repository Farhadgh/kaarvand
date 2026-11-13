"""Wallet operations.

Balances are stored in IRR (the unit every Iranian gateway expects) and shown in
Toman by the client. Every mutation writes a ``wallet_transactions`` row so the
balance can always be reconstructed and audited.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import Wallet, WalletTransaction

TOMAN = 10  # 1 Toman = 10 Rial


class InsufficientBalanceError(AppError):
    def __init__(self, *, balance_irr: int, needed_irr: int) -> None:
        super().__init__(
            code="wallet.insufficient_balance",
            status_code=402,
            params={"balance_irr": balance_irr, "needed_irr": needed_irr},
        )


async def get_or_create_wallet(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Wallet:
    wallet = (
        await db.execute(select(Wallet).where(Wallet.user_id == user_id))
    ).scalar_one_or_none()
    if wallet is not None:
        return wallet

    wallet = Wallet(org_id=org_id, user_id=user_id, balance_irr=0, currency="IRR", is_enabled=True)
    db.add(wallet)
    await db.flush()
    return wallet


async def get_wallet_for_user(db: AsyncSession, user_id: uuid.UUID) -> Wallet | None:
    return (
        await db.execute(select(Wallet).where(Wallet.user_id == user_id))
    ).scalar_one_or_none()


async def credit(
    db: AsyncSession,
    wallet: Wallet,
    *,
    amount_irr: int,
    kind: str,
    ref: str | None = None,
    note: str | None = None,
) -> WalletTransaction:
    if amount_irr <= 0:
        raise AppError(code="wallet.invalid_amount", status_code=422)
    wallet.balance_irr = int(wallet.balance_irr) + int(amount_irr)
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount_irr=int(amount_irr),
        kind=kind,
        ref=ref,
        note=note,
    )
    db.add(tx)
    await db.flush()
    return tx


async def debit(
    db: AsyncSession,
    wallet: Wallet,
    *,
    amount_irr: int,
    kind: str,
    ref: str | None = None,
    note: str | None = None,
    allow_negative: bool = False,
) -> WalletTransaction:
    if amount_irr <= 0:
        raise AppError(code="wallet.invalid_amount", status_code=422)
    if not allow_negative and int(wallet.balance_irr) < int(amount_irr):
        raise InsufficientBalanceError(
            balance_irr=int(wallet.balance_irr), needed_irr=int(amount_irr)
        )
    wallet.balance_irr = int(wallet.balance_irr) - int(amount_irr)
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount_irr=-int(amount_irr),
        kind=kind,
        ref=ref,
        note=note,
    )
    db.add(tx)
    await db.flush()
    return tx


async def recent_transactions(
    db: AsyncSession, wallet_id: uuid.UUID, *, limit: int = 50
) -> list[WalletTransaction]:
    rows = (
        await db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    return list(rows)
