"""v1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    apps,
    audio,
    auth,
    billing,
    catalog,
    connector_ws,
    devices,
    inbound,
    meta,
    models,
    otp,
    payments,
    prompts,
    providers,
    runs,
    tools,
    usage,
    users,
    wallet,
)
from app.api.v1 import (
    settings as settings_api,
)

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(otp.router)
api_router.include_router(wallet.router)
api_router.include_router(billing.router)
api_router.include_router(payments.router)
api_router.include_router(catalog.router)
api_router.include_router(providers.router)
api_router.include_router(models.router)
api_router.include_router(prompts.router)
api_router.include_router(agents.router)
api_router.include_router(tools.router)
api_router.include_router(apps.router)
api_router.include_router(inbound.router)
api_router.include_router(audio.router)
api_router.include_router(runs.router)
api_router.include_router(devices.router)
api_router.include_router(connector_ws.router)
api_router.include_router(usage.router)
api_router.include_router(users.router)
api_router.include_router(settings_api.router)
