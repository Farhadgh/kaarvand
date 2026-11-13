"""Customer facing model catalog: Persian names, Toman prices, no provider data.

``/v1/models`` is the admin view (USD prices, provider ids, sync state). This
router is the only model surface a customer may call, and it is built so that
nothing about where a model is hosted can leak:

* provider id / name / ``base_url`` / health are never selected;
* prices are USD in the database and are converted here, with the same markup
  helper billing uses, to **Toman per 1M tokens** (or per minute / 1k chars);
* disabled models and models of disabled providers are invisible.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.models import audio_kind_of
from app.billing.fx import current_fx_rate
from app.billing.pricing import retail_prices
from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_member
from app.core.errors import NotFoundError
from app.db.models import Model, Provider, User
from app.schemas.catalog import CatalogModelOut

router = APIRouter(prefix="/catalog", tags=["catalog"])

Capability = Literal["tools", "vision", "audio", "reasoning", "stream"]
Modality = Literal["text", "image", "audio"]


def _capabilities(model: Model) -> list[str]:
    flags = {
        "tools": model.supports_tools,
        "vision": model.supports_vision,
        "audio": model.supports_audio,
        "reasoning": model.supports_reasoning,
        "stream": model.supports_stream,
    }
    return [name for name, enabled in flags.items() if enabled]


def catalog_out(
    model: Model,
    *,
    fx_rate: int,
    settings: Settings,
) -> CatalogModelOut:
    prices = retail_prices(model, fx_rate=fx_rate, settings=settings)
    kind = audio_kind_of(model)
    if kind == "stt":
        unit = "per_minute"
    elif kind == "tts":
        unit = "per_1k_chars"
    else:
        unit = "per_1m_tokens"

    persian = None
    if kind is not None:
        from app.audio.service import persian_level

        persian = persian_level(model, kind)

    return CatalogModelOut(
        id=model.id,
        name=model.display_name_fa or model.external_id,
        family=model.family,
        context_window=model.context_window,
        max_output=model.max_output,
        modalities=list(model.modalities or []),
        capabilities=_capabilities(model),
        audio_kind=kind,
        audio_chat=bool(model.supports_audio and kind is None),
        persian=persian,
        billing_unit=unit,
        price_known=any(value is not None for value in prices.values()),
        **prices,
    )


def _base_query(user: User):
    return (
        select(Model)
        .join(Provider, Provider.id == Model.provider_id)
        .where(
            Provider.org_id == user.org_id,
            Provider.is_enabled.is_(True),
            Model.is_enabled.is_(True),
        )
    )


@router.get("/models", response_model=list[CatalogModelOut])
async def list_catalog(
    capability: Capability | None = None,
    modality: Modality | None = None,
    family: str | None = Query(default=None, max_length=80),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_member),
    settings: Settings = Depends(get_settings),
) -> list[CatalogModelOut]:
    stmt = _base_query(user)
    if capability == "tools":
        stmt = stmt.where(Model.supports_tools.is_(True))
    elif capability == "vision":
        stmt = stmt.where(Model.supports_vision.is_(True))
    elif capability == "audio":
        stmt = stmt.where(Model.supports_audio.is_(True))
    elif capability == "reasoning":
        stmt = stmt.where(Model.supports_reasoning.is_(True))
    elif capability == "stream":
        stmt = stmt.where(Model.supports_stream.is_(True))
    if modality is not None:
        stmt = stmt.where(Model.modalities.contains([modality]))
    if family:
        stmt = stmt.where(Model.family == family)
    if q:
        from app.core.text_fa import normalize_fa

        needle = f"%{normalize_fa(q)}%"
        stmt = stmt.where(
            Model.external_id.ilike(needle)
            | Model.display_name_fa.ilike(needle)
            | Model.family.ilike(needle)
        )

    stmt = stmt.order_by(Model.family, Model.external_id).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()

    fx_rate = await current_fx_rate(db, settings)
    return [catalog_out(row, fx_rate=fx_rate, settings=settings) for row in rows]


@router.get("/models/{model_id}", response_model=CatalogModelOut)
async def read_catalog_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_member),
    settings: Settings = Depends(get_settings),
) -> CatalogModelOut:
    model = (
        await db.execute(_base_query(user).where(Model.id == model_id))
    ).scalar_one_or_none()
    if model is None:
        raise NotFoundError(code="model.not_found")
    fx_rate = await current_fx_rate(db, settings)
    return catalog_out(model, fx_rate=fx_rate, settings=settings)
