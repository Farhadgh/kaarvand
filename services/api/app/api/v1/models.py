"""Model catalog endpoints: browse, tune, price."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.cost import price_model_usage
from app.billing.fx import current_fx_rate
from app.core.config import Settings, get_settings
from app.core.deps import get_db, require_admin
from app.core.errors import AppError, NotFoundError
from app.db.models import Model, PriceHistory, Provider, User
from app.providers.gateway import stream_model
from app.providers.sync import apply_manual_price
from app.schemas.providers import (
    ManualPriceIn,
    ModelCreate,
    ModelOut,
    ModelProbeIn,
    ModelProbeOut,
    ModelUpdate,
    PriceHistoryOut,
)

router = APIRouter(tags=["models"])
admin_only = require_admin

Capability = Literal["tools", "vision", "audio", "reasoning", "stream"]


async def get_model(db: AsyncSession, user: User, model_id: uuid.UUID) -> Model:
    model = (
        await db.execute(
            select(Model)
            .join(Provider, Provider.id == Model.provider_id)
            .where(Model.id == model_id, Provider.org_id == user.org_id)
        )
    ).scalar_one_or_none()
    if model is None:
        raise NotFoundError(code="model.not_found")
    return model


def audio_kind_of(model: Model) -> str | None:
    """``stt``/``tts`` for speech models (explicit meta first, then the model id)."""
    if not model.supports_audio:
        return None
    from app.audio.service import infer_kind

    return infer_kind(model.external_id, model.meta)


def model_out(model: Model) -> ModelOut:
    out = ModelOut.model_validate(model)
    out.audio_kind = audio_kind_of(model)
    # a model that accepts audio in chat but has no dedicated speech endpoint
    out.audio_chat = bool(model.supports_audio and out.audio_kind is None)
    if out.audio_kind is not None:
        from app.audio.service import persian_level

        out.persian = persian_level(model, out.audio_kind)
    return out


@router.get("/models", response_model=list[ModelOut])
async def list_models(
    provider_id: uuid.UUID | None = None,
    capability: Capability | None = None,
    q: str | None = Query(default=None, max_length=120),
    enabled_only: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> list[ModelOut]:
    stmt = (
        select(Model)
        .join(Provider, Provider.id == Model.provider_id)
        .where(Provider.org_id == user.org_id)
    )
    if provider_id:
        stmt = stmt.where(Model.provider_id == provider_id)
    if enabled_only:
        stmt = stmt.where(Model.is_enabled.is_(True), Provider.is_enabled.is_(True))
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
    return [model_out(row) for row in rows]


@router.get("/models/{model_id}", response_model=ModelOut)
async def read_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ModelOut:
    return model_out(await get_model(db, user, model_id))


@router.patch("/models/{model_id}", response_model=ModelOut)
async def update_model(
    model_id: uuid.UUID,
    payload: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ModelOut:
    model = await get_model(db, user, model_id)
    changes = payload.model_dump(exclude_unset=True)
    persian = changes.pop("persian", None)
    for key, value in changes.items():
        setattr(model, key, value)
    if persian is not None:
        # the Persian verdict is a manual override stored next to the probe data
        meta = dict(model.meta or {})
        if persian == "unknown":
            meta.pop("persian", None)
        else:
            meta["persian"] = persian
        model.meta = meta
    await db.flush()
    return model_out(model)


@router.post("/models/{model_id}/price", response_model=PriceHistoryOut)
async def set_manual_price(
    model_id: uuid.UUID,
    payload: ManualPriceIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> PriceHistoryOut:
    model = await get_model(db, user, model_id)
    entry = await apply_manual_price(
        db,
        model,
        input_price=payload.input_price,
        output_price=payload.output_price,
        cached_input_price=payload.cached_input_price,
        image_price=payload.image_price,
        audio_input_price=payload.audio_input_price,
        audio_output_price=payload.audio_output_price,
        currency=payload.currency,
        note=payload.note,
    )
    return PriceHistoryOut.model_validate(entry)


@router.post("/models", response_model=ModelOut, status_code=201)
async def create_model(
    payload: ModelCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> ModelOut:
    """Add a catalog entry by hand (used for speech models a provider omits)."""
    provider = await db.get(Provider, payload.provider_id)
    if provider is None or provider.org_id != user.org_id:
        raise NotFoundError(code="provider.not_found")

    exists = (
        await db.execute(
            select(Model).where(
                Model.provider_id == provider.id, Model.external_id == payload.external_id
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise AppError(
            code="model.exists",
            status_code=409,
            params={"external_id": payload.external_id},
        )

    meta: dict[str, Any] = {}
    if payload.audio_kind:
        meta["audio_kind"] = payload.audio_kind
    if payload.voices:
        meta["voices"] = payload.voices
    if payload.persian and payload.persian != "unknown":
        meta["persian"] = payload.persian

    model = Model(
        provider_id=provider.id,
        external_id=payload.external_id,
        display_name_fa=payload.display_name_fa,
        family=payload.family,
        supports_audio=payload.audio_kind is not None,
        supports_tools=not payload.audio_kind,
        supports_stream=not payload.audio_kind,
        input_price=payload.input_price,
        output_price=payload.output_price,
        audio_input_price=payload.audio_input_price,
        audio_output_price=payload.audio_output_price,
        price_unit="per_minute" if payload.audio_kind == "stt" else "per_token",
        price_source="manual",
        is_enabled=payload.is_enabled,
        modalities=["text", "audio"] if payload.audio_kind else ["text"],
        meta=meta,
    )
    db.add(model)
    await db.flush()
    return model_out(model)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> None:
    model = await get_model(db, user, model_id)
    await db.delete(model)
    await db.flush()


@router.get("/models/{model_id}/prices", response_model=list[PriceHistoryOut])
async def price_history(
    model_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
) -> list[PriceHistoryOut]:
    model = await get_model(db, user, model_id)
    rows = (
        (
            await db.execute(
                select(PriceHistory)
                .where(PriceHistory.model_id == model.id)
                .order_by(PriceHistory.effective_from.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [PriceHistoryOut.model_validate(row) for row in rows]


@router.post("/models/{model_id}/probe", response_model=ModelProbeOut)
async def probe_model(
    model_id: uuid.UUID,
    payload: ModelProbeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(admin_only),
    settings: Settings = Depends(get_settings),
) -> ModelProbeOut:
    """Real (billable) call through the gateway: streaming + cost in one shot."""
    model = await get_model(db, user, model_id)

    parts: list[str] = []
    tokens_in = 0
    tokens_out = 0
    fallback_used = False
    failure = None

    async for chunk in stream_model(
        db,
        model=model,
        messages=[{"role": "user", "content": payload.prompt}],
        max_tokens=payload.max_tokens,
    ):
        if chunk.type == "text" and chunk.text:
            parts.append(chunk.text)
        elif chunk.type == "usage":
            tokens_in = chunk.tokens_in or 0
            tokens_out = chunk.tokens_out or 0
        elif chunk.type == "notice":
            fallback_used = True
        elif chunk.type == "error":
            failure = chunk

    if failure is not None:
        raise AppError(
            code=failure.error_code or "provider.call_failed",
            status_code=502,
            params={"detail": failure.detail},
        )

    fx_rate = await current_fx_rate(db, settings)
    cost_usd, cost_irr = price_model_usage(
        model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        fx_rate=fx_rate,
    )
    return ModelProbeOut(
        text="".join(parts),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        cost_irr=cost_irr,
        fx_rate=fx_rate,
        fallback_used=fallback_used,
    )
