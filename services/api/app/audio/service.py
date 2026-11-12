"""Audio service: model resolution, provider calls, cost and ledger.

STT is billed per audio minute (``models.audio_input_price``), TTS per 1000
characters (``models.audio_output_price``). Both fall back to zero cost when the
model has no audio price, so a fresh install never crashes on a missing price.
"""

from __future__ import annotations

import math
import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.cost import price_audio_usage
from app.billing.fx import current_fx_rate
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.db.models import Model, Organization, Provider, UsageLedger, User
from app.providers.registry import get_adapter
from app.runtime.budget import spent_this_month_irr

from .languages import persian_of as _persian_of

STT = "stt"
TTS = "tts"

MAX_UPLOAD_MB = 25
MAX_TTS_CHARS = 4000

# OpenAI (and compatible) TTS voices; a model may override via meta.voices
DEFAULT_VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
]

_STT_RE = re.compile(
    r"whisper|transcrib|\bstt\b|\basr\b|scribe|parakeet|chirp|speech[-_ ]?to[-_ ]?text",
    re.IGNORECASE,
)
_TTS_RE = re.compile(
    r"\btts\b|text[-_ ]?to[-_ ]?speech|tts-\d|mini-tts|\bvoice\b|eleven|kokoro|aura-\d",
    re.IGNORECASE,
)


def infer_kind(external_id: str, meta: dict[str, Any] | None = None) -> str | None:
    """Which audio API a model speaks: explicit ``meta.audio_kind`` wins, then id."""
    explicit = (meta or {}).get("audio_kind")
    if explicit in (STT, TTS):
        return str(explicit)
    if _STT_RE.search(external_id):
        return STT
    if _TTS_RE.search(external_id):
        return TTS
    return None


def voices_of(model: Model) -> list[str]:
    configured = (model.meta or {}).get("voices")
    if isinstance(configured, list) and configured:
        return [str(item) for item in configured]
    return DEFAULT_VOICES if infer_kind(model.external_id, model.meta) == TTS else []


def persian_of(model: Model, kind: str | None = None) -> dict[str, Any] | None:
    """Persian verdict for a model (manual override -> probe cache -> table)."""
    resolved = kind or infer_kind(model.external_id, model.meta)
    return _persian_of(model.external_id, model.meta, kind=resolved)


def persian_level(model: Model, kind: str | None = None) -> str | None:
    info = persian_of(model, kind)
    return str(info["level"]) if info else None


async def resolve_audio_model(
    db: AsyncSession,
    user: User,
    model_id: uuid.UUID,
    *,
    expected: str,
) -> tuple[Model, Provider, str]:
    """Load the model + provider and make sure it can do the requested job."""
    row = (
        await db.execute(
            select(Model, Provider)
            .join(Provider, Provider.id == Model.provider_id)
            .where(Model.id == model_id, Provider.org_id == user.org_id)
        )
    ).first()
    if row is None:
        raise NotFoundError(code="model.not_found")
    model, provider = row[0], row[1]

    if not model.supports_audio:
        raise AppError(
            code="audio.not_audio_model",
            status_code=422,
            params={"model": model.external_id},
        )
    kind = infer_kind(model.external_id, model.meta)
    if kind is None:
        raise AppError(
            code="audio.unknown_kind",
            status_code=422,
            params={"model": model.external_id, "hint": "meta.audio_kind = stt|tts"},
        )
    if kind != expected:
        raise AppError(
            code="audio.wrong_kind",
            status_code=422,
            params={"model": model.external_id, "expected": expected, "actual": kind},
        )
    if not provider.is_enabled:
        raise AppError(
            code="provider.disabled", status_code=409, params={"provider": provider.slug}
        )
    return model, provider, kind


async def ensure_org_budget(db: AsyncSession, user: User) -> None:
    org = await db.get(Organization, user.org_id)
    budget = getattr(org, "monthly_budget_irr", None) if org else None
    if not budget:
        return
    spent = await spent_this_month_irr(db, org_id=user.org_id)
    if spent >= int(budget):
        raise AppError(
            code="budget.org_exceeded",
            status_code=409,
            params={"spent_irr": spent, "budget_irr": int(budget)},
        )


async def _record(
    db: AsyncSession,
    *,
    user: User,
    model: Model,
    provider: Provider,
    settings: Settings,
    fx_rate: Decimal,
    cost_usd: Decimal,
    cost_irr: int,
    audio_seconds: int = 0,
    audio_chars: int = 0,
) -> bool:
    billable = not settings.free_mode
    db.add(
        UsageLedger(
            org_id=user.org_id,
            provider_id=provider.id,
            model_id=model.id,
            tokens_in=0,
            tokens_out=0,
            audio_seconds=max(int(audio_seconds), 0),
            audio_chars=max(int(audio_chars), 0),
            cost_usd=cost_usd,
            markup_percent=model.markup_percent or Decimal("0"),
            fx_rate=fx_rate,
            cost_irr=cost_irr,
            billable=billable,
        )
    )
    await db.flush()
    return billable


async def transcribe(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    model_id: uuid.UUID,
    content: bytes,
    filename: str,
    mime: str | None,
    language: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Speech-to-text: returns text + real duration + cost."""
    if not content:
        raise AppError(code="audio.empty_file", status_code=422)
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError(
            code="audio.file_too_large", status_code=413, params={"max_mb": MAX_UPLOAD_MB}
        )

    model, provider, _ = await resolve_audio_model(db, user, model_id, expected=STT)
    await ensure_org_budget(db, user)

    adapter = get_adapter(provider.kind)
    transcribe_call = getattr(adapter, "transcribe", None)
    if transcribe_call is None:
        raise AppError(
            code="audio.unsupported_provider", status_code=422, params={"kind": provider.kind}
        )

    result = await transcribe_call(
        provider,
        model=model.external_id,
        content=content,
        filename=filename or "audio.webm",
        mime=mime,
        language=language,
        prompt=prompt,
    )

    duration = float(result.get("duration") or 0.0)
    billed_seconds = int(math.ceil(duration)) if duration > 0 else 0
    fx_rate = await current_fx_rate(db, settings)
    cost_usd, cost_irr = price_audio_usage(model, audio_seconds=billed_seconds, fx_rate=fx_rate)
    billable = await _record(
        db,
        user=user,
        model=model,
        provider=provider,
        settings=settings,
        fx_rate=fx_rate,
        cost_usd=cost_usd,
        cost_irr=cost_irr,
        audio_seconds=billed_seconds,
    )
    return {
        "model_id": model.id,
        "text": str(result.get("text") or ""),
        "language": result.get("language"),
        "seconds": duration,
        "cost_usd": cost_usd,
        "cost_irr": cost_irr,
        "fx_rate": fx_rate,
        "billable": billable,
    }


async def synthesize(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    model_id: uuid.UUID,
    text: str,
    voice: str = "alloy",
    fmt: str = "mp3",
    speed: float | None = None,
) -> tuple[bytes, str, dict[str, Any]]:
    """Text-to-speech: returns (audio bytes, mime type, meta with cost)."""
    clean = (text or "").strip()
    if not clean:
        raise AppError(code="audio.empty_text", status_code=422)
    if len(clean) > MAX_TTS_CHARS:
        raise AppError(
            code="audio.text_too_long",
            status_code=413,
            params={"max_chars": MAX_TTS_CHARS, "chars": len(clean)},
        )

    model, provider, _ = await resolve_audio_model(db, user, model_id, expected=TTS)
    await ensure_org_budget(db, user)

    adapter = get_adapter(provider.kind)
    speech_call = getattr(adapter, "speech", None)
    if speech_call is None:
        raise AppError(
            code="audio.unsupported_provider", status_code=422, params={"kind": provider.kind}
        )

    # A model only accepts its own voice names (``alloy`` is OpenAI-only); when the
    # panel sends a stale/unsupported voice we fall back to the first supported one
    # instead of letting the provider reject the whole request.
    available = voices_of(model)
    voice_used = voice or "alloy"
    if available and voice_used not in available:
        voice_used = available[0]

    audio, mime = await speech_call(
        provider,
        model=model.external_id,
        text=clean,
        voice=voice_used,
        fmt=fmt,
        speed=speed,
    )

    # The provider may have forced a different container (PCM is wrapped into WAV).
    delivered = "wav" if mime == "audio/wav" else fmt

    chars = len(clean)
    fx_rate = await current_fx_rate(db, settings)
    cost_usd, cost_irr = price_audio_usage(model, audio_chars=chars, fx_rate=fx_rate)
    billable = await _record(
        db,
        user=user,
        model=model,
        provider=provider,
        settings=settings,
        fx_rate=fx_rate,
        cost_usd=cost_usd,
        cost_irr=cost_irr,
        audio_chars=chars,
    )
    meta = {
        "model_id": model.id,
        "chars": chars,
        "format": delivered,
        "voice": voice_used,
        "cost_usd": cost_usd,
        "cost_irr": cost_irr,
        "fx_rate": fx_rate,
        "billable": billable,
    }
    return audio, mime, meta
