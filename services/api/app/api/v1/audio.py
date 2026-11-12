"""Audio endpoints: STT (transcriptions) and TTS (speech).

Both go through the same provider adapters as chat, so credentials, proxies and
pricing live in one place. Cost is per audio minute (STT) or per 1K characters
(TTS) and is written to the usage ledger.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio import service as audio
from app.audio.languages import LEVEL_LABELS_FA
from app.core.config import Settings, get_settings
from app.core.deps import get_current_user, get_db, require_roles
from app.db.models import Model, Provider, User
from app.schemas.audio import (
    AudioMetaOut,
    AudioModelOut,
    AudioPresetOut,
    SpeechIn,
    SpeechMeta,
    TranscriptionOut,
)
from app.seeding.audio_presets import AUDIO_PRESETS

router = APIRouter(tags=["audio"])
operator = require_roles("owner", "admin", "operator")

FORMATS = ["mp3", "wav", "opus", "aac", "flac", "pcm"]

#: Panel ordering: Persian-capable models first, then good, weak, unknown, none.
_PERSIAN_ORDER = {"verified": 0, "good": 1, "weak": 2, None: 3, "none": 4}


@router.get("/audio/meta", response_model=AudioMetaOut)
async def audio_meta(_: User = Depends(get_current_user)) -> AudioMetaOut:
    return AudioMetaOut(
        max_upload_mb=audio.MAX_UPLOAD_MB,
        max_tts_chars=audio.MAX_TTS_CHARS,
        voices=audio.DEFAULT_VOICES,
        formats=FORMATS,
        kinds={
            "stt": "تبدیل گفتار به متن (whisper / transcribe)",
            "tts": "تبدیل متن به گفتار (tts / speech)",
        },
        persian_levels=LEVEL_LABELS_FA,
    )


@router.get("/audio/presets", response_model=list[AudioPresetOut])
async def audio_presets(_: User = Depends(get_current_user)) -> list[AudioPresetOut]:
    """One click presets for speech models a provider's catalog may omit."""
    return [AudioPresetOut(**preset) for preset in AUDIO_PRESETS]


@router.get("/audio/models", response_model=list[AudioModelOut])
async def list_audio_models(
    kind: Literal["stt", "tts"] | None = Query(default=None),
    persian: Literal["verified", "good", "weak", "none", "any"] | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AudioModelOut]:
    rows = (
        await db.execute(
            select(Model, Provider)
            .join(Provider, Provider.id == Model.provider_id)
            .where(
                Provider.org_id == user.org_id,
                Model.supports_audio.is_(True),
            )
            .order_by(Model.external_id)
        )
    ).all()

    out: list[AudioModelOut] = []
    for model, provider in rows:
        inferred = audio.infer_kind(model.external_id, model.meta)
        if inferred is None:
            continue
        if kind and inferred != kind:
            continue
        info = audio.persian_of(model, inferred)
        if persian == "any":
            if info is None:
                continue
        elif persian and (info or {}).get("level") != persian:
            continue
        out.append(
            AudioModelOut(
                id=model.id,
                provider_id=provider.id,
                provider_name=provider.name,
                external_id=model.external_id,
                display_name_fa=model.display_name_fa,
                kind=inferred,  # type: ignore[arg-type]
                voices=audio.voices_of(model),
                audio_input_price=model.audio_input_price,
                audio_output_price=model.audio_output_price,
                is_enabled=model.is_enabled and provider.is_enabled,
                persian=(info or {}).get("level"),  # type: ignore[arg-type]
                persian_score=(info or {}).get("score"),
                persian_note_fa=(info or {}).get("label_fa"),
            )
        )

    # Persian-capable models first: an operator looking for a usable voice should
    # never have to scroll past ten models that cannot speak Persian at all.
    out.sort(
        key=lambda row: (
            _PERSIAN_ORDER.get(row.persian, 3),
            row.kind,
            row.external_id,
        )
    )
    return out


@router.post("/audio/transcriptions", response_model=TranscriptionOut)
async def create_transcription(
    file: UploadFile = File(...),
    model_id: uuid.UUID = Form(...),
    language: str | None = Form(default=None, max_length=10),
    prompt: str | None = Form(default=None, max_length=1000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(operator),
    settings: Settings = Depends(get_settings),
) -> TranscriptionOut:
    limit = audio.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(limit + 1)
    result = await audio.transcribe(
        db,
        user=user,
        settings=settings,
        model_id=model_id,
        content=content,
        filename=file.filename or "audio.webm",
        mime=file.content_type,
        language=language or None,
        prompt=prompt or None,
    )
    return TranscriptionOut(**result)


@router.post("/audio/speech")
async def create_speech(
    payload: SpeechIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(operator),
    settings: Settings = Depends(get_settings),
) -> Response:
    audio_bytes, mime, meta = await audio.synthesize(
        db,
        user=user,
        settings=settings,
        model_id=payload.model_id,
        text=payload.text,
        voice=payload.voice,
        fmt=payload.format,
        speed=payload.speed,
    )
    # the provider may have forced another container (PCM is wrapped into WAV)
    delivered = str(meta.get("format") or payload.format)
    filename = f"kaarvand-speech-{uuid.uuid4().hex[:8]}.{delivered}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Audio-Format": delivered,
        "X-Audio-Voice": str(meta.get("voice") or payload.voice),
        "X-Cost-Usd": str(meta["cost_usd"]),
        "X-Cost-Irr": str(meta["cost_irr"]),
        "X-Fx-Rate": str(meta["fx_rate"]),
        "X-Chars": str(meta["chars"]),
        "Cache-Control": "no-store",
    }
    return Response(content=audio_bytes, media_type=mime, headers=headers)


@router.get("/audio/speech/estimate", response_model=SpeechMeta)
async def estimate_speech(
    model_id: uuid.UUID,
    text: str = Query(min_length=1, max_length=audio.MAX_TTS_CHARS),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SpeechMeta:
    """Price a TTS request without calling the provider (for the panel preview)."""
    model, _provider, _kind = await audio.resolve_audio_model(
        db, user, model_id, expected=audio.TTS
    )
    from app.billing.cost import price_audio_usage
    from app.billing.fx import current_fx_rate

    fx_rate = await current_fx_rate(db, settings)
    cost_usd, cost_irr = price_audio_usage(model, audio_chars=len(text), fx_rate=fx_rate)
    return SpeechMeta(
        model_id=model.id,
        chars=len(text),
        cost_usd=cost_usd,
        cost_irr=cost_irr,
        fx_rate=fx_rate,
        billable=not settings.free_mode,
    )
