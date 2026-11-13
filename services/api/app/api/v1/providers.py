"""Provider CRUD (admin only)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_admin
from app.core.errors import AppError, NotFoundError
from app.db.models import Provider, ProviderAdapter, User
from app.providers.credentials import encrypt_api_key, masked_api_key, scrub
from app.providers.registry import get_adapter, known_kinds
from app.providers.sync import sync_models, sync_prices
from app.schemas.providers import (
    ConnectionTestOut,
    ProviderAdapterOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    SyncModelsOut,
    SyncPricesOut,
)

router = APIRouter(tags=["providers"])
admin_only = require_admin


def slugify(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (candidate[:50] or "provider").strip("-")


async def unique_slug(db: AsyncSession, org_id: uuid.UUID, wanted: str) -> str:
    candidate = wanted
    counter = 1
    while True:
        found = (
            await db.execute(
                select(Provider.id).where(Provider.org_id == org_id, Provider.slug == candidate)
            )
        ).first()
        if found is None:
            return candidate
        counter += 1
        candidate = f"{wanted}-{counter}"


def to_out(provider: Provider) -> ProviderOut:
    data = ProviderOut.model_validate(provider)
    data.has_credentials = bool(provider.credentials_enc)
    try:
        data.api_key_masked = masked_api_key(provider)
    except Exception:  # noqa: BLE001 - a wrong master key must not break listing
        data.api_key_masked = None
    return data


async def get_provider(db: AsyncSession, user: User, provider_id: uuid.UUID) -> Provider:
    provider = (
        await db.execute(
            select(Provider).where(Provider.id == provider_id, Provider.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if provider is None:
        raise NotFoundError(code="provider.not_found")
    return provider


@router.get("/provider-adapters", response_model=list[ProviderAdapterOut])
async def list_adapters(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
) -> list[ProviderAdapterOut]:
    rows = (
        (
            await db.execute(
                select(ProviderAdapter)
                .where(ProviderAdapter.is_enabled.is_(True))
                .order_by(ProviderAdapter.kind)
            )
        )
        .scalars()
        .all()
    )
    return [ProviderAdapterOut.model_validate(row) for row in rows]


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> list[ProviderOut]:
    rows = (
        (
            await db.execute(
                select(Provider)
                .where(Provider.org_id == user.org_id)
                .order_by(Provider.priority, Provider.name)
            )
        )
        .scalars()
        .all()
    )
    return [to_out(row) for row in rows]


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ProviderOut:
    if payload.kind not in known_kinds():
        raise AppError(
            code="provider.unknown_kind",
            status_code=400,
            params={"kind": payload.kind, "supported": known_kinds()},
        )

    provider = Provider(
        org_id=user.org_id,
        name=payload.name,
        slug=await unique_slug(db, user.org_id, payload.slug or slugify(payload.name)),
        kind=payload.kind,
        base_url=payload.base_url,
        auth_type=payload.auth_type,
        extra_headers=payload.extra_headers,
        models_url=payload.models_url,
        prices_url=payload.prices_url,
        priority=payload.priority,
        is_enabled=payload.is_enabled,
        chat_spec=payload.chat_spec,
        response_map=payload.response_map,
        meta=payload.meta,
    )
    db.add(provider)
    await db.flush()
    provider.credentials_enc = encrypt_api_key(provider, payload.api_key)
    await db.flush()
    return to_out(provider)


@router.get("/providers/{provider_id}", response_model=ProviderOut)
async def read_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ProviderOut:
    return to_out(await get_provider(db, user, provider_id))


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ProviderOut:
    provider = await get_provider(db, user, provider_id)
    data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    for key, value in data.items():
        setattr(provider, key, value)
    if api_key is not None:
        provider.credentials_enc = encrypt_api_key(provider, api_key)
    await db.flush()
    return to_out(provider)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> Response:
    provider = await get_provider(db, user, provider_id)
    await db.delete(provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/providers/{provider_id}/test", response_model=ConnectionTestOut)
async def test_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ConnectionTestOut:
    provider = await get_provider(db, user, provider_id)
    result = await get_adapter(provider.kind).test(provider)
    provider.health = "ok" if result.ok else "error"
    provider.health_message = result.detail
    await db.flush()
    return ConnectionTestOut(
        ok=result.ok,
        latency_ms=result.latency_ms,
        error_code=result.error_code,
        detail=result.detail,
        models_seen=result.models_seen,
    )


@router.post("/providers/{provider_id}/sync-models", response_model=SyncModelsOut)
async def run_sync_models(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> SyncModelsOut:
    provider = await get_provider(db, user, provider_id)
    try:
        created, updated, total = await sync_models(db, provider)
    except Exception as exc:  # noqa: BLE001 - any upstream error becomes a code
        provider.health = "error"
        provider.health_message = scrub(provider, str(exc))
        raise AppError(
            code="provider.sync_failed",
            status_code=502,
            params={"detail": provider.health_message},
        ) from exc
    provider.health = "ok"
    provider.health_message = None
    return SyncModelsOut(created=created, updated=updated, total=total)


@router.post("/providers/{provider_id}/sync-prices", response_model=SyncPricesOut)
async def run_sync_prices(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> SyncPricesOut:
    provider = await get_provider(db, user, provider_id)
    try:
        updated, source = await sync_prices(db, provider)
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            code="provider.price_sync_failed",
            status_code=502,
            params={"detail": scrub(provider, str(exc))},
        ) from exc
    return SyncPricesOut(updated=updated, source=source)
