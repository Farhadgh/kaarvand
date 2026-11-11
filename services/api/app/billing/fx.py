"""Exchange rate (USD -> IRR) stored in the database and editable from the panel."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import AppSetting

FX_KEY = "fx"


async def current_fx_rate(db: AsyncSession, settings: Settings | None = None) -> int:
    """Database value wins; the env var is only the bootstrap default."""
    row = (
        await db.execute(select(AppSetting).where(AppSetting.key == FX_KEY))
    ).scalar_one_or_none()
    fallback = int((settings or get_settings()).fx_usd_irr)
    if row and isinstance(row.value, dict):
        rate = row.value.get("usd_irr")
        if isinstance(rate, int | float | str):
            try:
                value = int(rate)
            except (TypeError, ValueError):
                value = 0
            # 0 means "not configured yet" -> fall back to the environment default
            if value > 0:
                return value
    return fallback


async def set_fx_rate(
    db: AsyncSession,
    *,
    usd_irr: int,
    user_id: uuid.UUID | None = None,
    source: str = "manual",
) -> int:
    row = (
        await db.execute(select(AppSetting).where(AppSetting.key == FX_KEY))
    ).scalar_one_or_none()
    value = {"usd_irr": int(usd_irr), "source": source}
    if row is None:
        db.add(AppSetting(key=FX_KEY, value=value, updated_by=user_id))
    else:
        row.value = value
        row.updated_by = user_id
        row.version += 1
    await db.flush()
    return int(usd_irr)


def to_decimal(rate: int | float | str) -> Decimal:
    return Decimal(str(rate or 0))
