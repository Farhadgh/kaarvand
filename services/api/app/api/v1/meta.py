"""Meta / health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.registry import get_gateway
from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.db.session import set_bypass_rls
from app.schemas.meta import HealthOut, MetaOut

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaOut)
async def meta(settings: Settings = Depends(get_settings)) -> MetaOut:
    gateway = get_gateway(settings)
    return MetaOut(
        app_name=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        locale=settings.default_locale,
        timezone=settings.default_timezone,
        calendar=settings.default_calendar,
        currency=settings.default_currency,
        digits=settings.default_digits,
        free_mode=settings.free_mode,
        billing_enabled=settings.billing_enabled,
        payment_gateway=gateway.name,  # type: ignore[attr-defined]
        payment_gateway_enabled=bool(getattr(gateway, "enabled", False)),
        fx_usd_irr=settings.fx_usd_irr,
        api_prefix=settings.api_prefix,
    )


@router.get("/healthz", response_model=HealthOut)
async def healthz(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthOut:
    await set_bypass_rls(db, True)
    await db.execute(text("select 1"))
    return HealthOut(status="ok", db="ok", version=settings.app_version)
