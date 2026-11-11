"""Billing endpoints. Phase 1: everything reports ``disabled`` (free mode)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.billing.registry import get_gateway
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.models import User

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status")
async def status(
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    gateway = get_gateway(settings)
    return {
        "gateway": gateway.name,  # type: ignore[attr-defined]
        "gateway_enabled": bool(getattr(gateway, "enabled", False)),
        "free_mode": settings.free_mode,
        "billing_enabled": settings.billing_enabled,
    }


@router.post("/checkout")
async def checkout(
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Proves the port works: with the noop gateway this always returns
    ``409 billing.disabled``. Wiring Zarinpal later changes nothing here."""
    gateway = get_gateway(settings)
    init = await gateway.create_payment(  # type: ignore[attr-defined]
        amount_irr=0,
        order_id="demo",
        callback_url="http://localhost:3000/billing/callback",
        description_fa="تست درگاه پرداخت",
    )
    return {"gateway": init.gateway, "token": init.token, "redirect_url": init.redirect_url}
