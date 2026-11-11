"""Settings: organization profile, personal preferences, exchange rate."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import get_org
from app.billing.fx import current_fx_rate, set_fx_rate
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db, require_roles
from app.db.models import User
from app.schemas.settings import (
    FxIn,
    FxOut,
    MeOut,
    MeUpdate,
    OrgOut,
    OrgUpdate,
    SettingsOut,
)

router = APIRouter(prefix="/settings", tags=["settings"])
admin_only = require_roles("owner", "admin")


@router.get("", response_model=SettingsOut)
async def read_settings(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SettingsOut:
    org = await get_org(db, user)
    fx = await current_fx_rate(db, settings)
    return SettingsOut(
        org=OrgOut.model_validate(org),
        me=MeOut.model_validate(user),
        fx=FxOut(usd_irr=fx),
        free_mode=settings.free_mode,
        billing_enabled=settings.billing_enabled,
        payment_gateway=settings.payment_gateway,
        version=settings.app_version,
        locale=org.settings.get("locale", settings.default_locale)
        if isinstance(org.settings, dict)
        else settings.default_locale,
        calendar=org.calendar,
        digits=org.digits,
        timezone=org.timezone,
    )


@router.patch("/org", response_model=OrgOut)
async def update_org(
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> OrgOut:
    org = await get_org(db, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, key, value)
    await db.flush()
    return OrgOut.model_validate(org)


@router.patch("/me", response_model=MeOut)
async def update_me(
    payload: MeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MeOut:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await db.flush()
    return MeOut.model_validate(user)


@router.patch("/fx", response_model=FxOut)
async def update_fx(
    payload: FxIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> FxOut:
    """Rates affect every future cost calculation (past ledger rows keep theirs)."""
    rate = await set_fx_rate(db, usd_irr=payload.usd_irr, user_id=user.id)
    return FxOut(usd_irr=rate)
