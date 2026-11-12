"""Audio endpoint schemas (STT / TTS)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

AudioKind = Literal["stt", "tts"]
#: ``pcm`` is offered because some models accept nothing else; the backend wraps
#: the raw samples into a WAV container before handing them to the caller.
AudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]
PersianLevel = Literal["verified", "good", "weak", "none", "unknown"]


class AudioModelOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str | None = None
    external_id: str
    display_name_fa: str | None = None
    kind: AudioKind
    voices: list[str] = Field(default_factory=list)
    audio_input_price: Decimal | None = None  # USD / audio minute (STT)
    audio_output_price: Decimal | None = None  # USD / 1K characters (TTS)
    is_enabled: bool = True
    #: Persian verdict measured by the TTS -> STT probe (``None`` = not checked).
    persian: PersianLevel | None = None
    persian_score: float | None = None
    persian_note_fa: str | None = None


class TranscriptionOut(BaseModel):
    model_id: uuid.UUID
    text: str
    language: str | None = None
    seconds: float = 0.0
    cost_usd: Decimal = Decimal("0")
    cost_irr: int = 0
    fx_rate: Decimal = Decimal("0")
    billable: bool = False


class SpeechIn(BaseModel):
    model_id: uuid.UUID
    text: str = Field(min_length=1, max_length=4000)
    voice: str = Field(default="alloy", max_length=40)
    format: AudioFormat = "mp3"
    speed: float | None = Field(default=None, ge=0.25, le=4.0)


class SpeechMeta(BaseModel):
    model_id: uuid.UUID
    chars: int
    cost_usd: Decimal = Decimal("0")
    cost_irr: int = 0
    fx_rate: Decimal = Decimal("0")
    billable: bool = False


class AudioPresetOut(BaseModel):
    """A ready-to-add speech model (see app.seeding.audio_presets)."""

    slug: str
    external_id: str
    label_fa: str
    kind: AudioKind
    audio_input_price: Decimal | None = None
    audio_output_price: Decimal | None = None
    vendor_hint: str | None = None
    persian: PersianLevel | None = None


class AudioMetaOut(BaseModel):
    """Small helper for the panel: limits and defaults it must respect."""

    max_upload_mb: int
    max_tts_chars: int
    voices: list[str]
    formats: list[str]
    kinds: dict[str, Any]
    #: level -> Persian sentence (so the panel never hard-codes the wording)
    persian_levels: dict[str, str] = Field(default_factory=dict)
