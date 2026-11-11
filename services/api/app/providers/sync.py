"""Model / price synchronisation (upsert driven by the adapter)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CapabilityRule, Model, PriceHistory, Provider
from app.providers.capabilities import infer_flags
from app.providers.registry import get_adapter


async def sync_models(db: AsyncSession, provider: Provider) -> tuple[int, int, int]:
    adapter = get_adapter(provider.kind)
    remote = await adapter.list_models(provider)

    rules = (
        (await db.execute(select(CapabilityRule).where(CapabilityRule.is_active.is_(True))))
        .scalars()
        .all()
    )
    existing = {
        model.external_id: model
        for model in (
            await db.execute(select(Model).where(Model.provider_id == provider.id))
        ).scalars()
    }

    created = 0
    updated = 0
    for item in remote:
        flags = infer_flags(item.external_id, rules)
        model = existing.get(item.external_id)
        if model is None:
            db.add(
                Model(
                    provider_id=provider.id,
                    external_id=item.external_id,
                    display_name_fa=item.display_name,
                    context_window=item.context_window,
                    max_output=item.max_output,
                    modalities=item.modalities or [],
                    meta=item.meta or {},
                    **flags,
                )
            )
            created += 1
            continue

        model.display_name_fa = model.display_name_fa or item.display_name
        model.context_window = item.context_window or model.context_window
        model.max_output = item.max_output or model.max_output
        if item.modalities:
            model.modalities = item.modalities
        for key, value in flags.items():
            if getattr(model, key) != value and key not in (model.meta or {}):
                setattr(model, key, value)
        if item.meta:
            model.meta = {**(model.meta or {}), **item.meta}
        updated += 1

    provider.last_synced_at = datetime.now(UTC)
    await db.flush()
    return created, updated, len(remote)


async def sync_prices(db: AsyncSession, provider: Provider) -> tuple[int, str]:
    adapter = get_adapter(provider.kind)
    remote = await adapter.fetch_prices(provider)
    if not remote:
        return 0, "none"

    models = {
        model.external_id: model
        for model in (
            await db.execute(select(Model).where(Model.provider_id == provider.id))
        ).scalars()
    }

    now = datetime.now(UTC)
    updated = 0
    sources: set[str] = set()
    for price in remote:
        model = models.get(price.external_id)
        if model is None:
            continue

        changed = (
            model.input_price != price.input_price
            or model.output_price != price.output_price
            or model.cached_input_price != price.cached_input_price
        )
        model.input_price = price.input_price
        model.output_price = price.output_price
        model.cached_input_price = price.cached_input_price
        model.price_currency = price.currency
        model.price_source = price.source
        model.price_synced_at = now
        sources.add(price.source)

        if changed:
            db.add(
                PriceHistory(
                    model_id=model.id,
                    effective_from=now,
                    input_price=price.input_price,
                    output_price=price.output_price,
                    cached_input_price=price.cached_input_price,
                    image_price=price.image_price,
                    currency=price.currency,
                    source=price.source,
                )
            )
            updated += 1

    await db.flush()
    return updated, ",".join(sorted(sources)) or "provider"


async def apply_manual_price(
    db: AsyncSession,
    model: Model,
    *,
    input_price: Decimal,
    output_price: Decimal,
    cached_input_price: Decimal | None,
    image_price: Decimal | None,
    currency: str,
    note: str | None,
) -> PriceHistory:
    now = datetime.now(UTC)
    model.input_price = input_price
    model.output_price = output_price
    model.cached_input_price = cached_input_price
    model.image_price = image_price
    model.price_currency = currency
    model.price_source = "manual"
    model.price_synced_at = now
    entry = PriceHistory(
        model_id=model.id,
        effective_from=now,
        input_price=input_price,
        output_price=output_price,
        cached_input_price=cached_input_price,
        image_price=image_price,
        currency=currency,
        source=f"manual:{note}" if note else "manual",
    )
    db.add(entry)
    await db.flush()
    return entry


def model_reference(provider: Provider, model: Model) -> dict[str, Any]:
    """Provider + model pair used by the gateway."""
    return {"provider": provider, "external_id": model.external_id}
