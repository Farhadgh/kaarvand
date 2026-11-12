"""Provider schemas (create/update/read)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

AuthType = Literal["bearer", "api_key_header", "query", "basic", "none"]


class ProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=32)
    base_url: str | None = None
    auth_type: AuthType = "bearer"
    extra_headers: dict[str, str] = Field(default_factory=dict)
    models_url: str | None = None
    prices_url: str | None = None
    priority: int = 100
    is_enabled: bool = True
    chat_spec: dict[str, Any] | None = None
    response_map: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("base_url", "models_url", "prices_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value


class ProviderCreate(ProviderBase):
    slug: str | None = Field(default=None, max_length=64)
    api_key: str | None = Field(default=None, max_length=4096)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = None
    auth_type: AuthType | None = None
    extra_headers: dict[str, str] | None = None
    models_url: str | None = None
    prices_url: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None
    chat_spec: dict[str, Any] | None = None
    response_map: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    api_key: str | None = Field(default=None, max_length=4096)


class ProviderOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    base_url: str | None
    auth_type: str
    extra_headers: dict[str, Any]
    models_url: str | None
    prices_url: str | None
    priority: int
    is_enabled: bool
    health: str
    health_message: str | None
    has_credentials: bool = False
    api_key_masked: str | None = None
    last_synced_at: Any | None = None


class ProviderAdapterOut(ORMModel):
    kind: str
    title_fa: str
    description_fa: str | None
    is_builtin: bool
    spec_schema: dict[str, Any]


class ConnectionTestOut(BaseModel):
    ok: bool
    latency_ms: int
    error_code: str | None = None
    detail: str | None = None
    models_seen: int | None = None


class SyncModelsOut(BaseModel):
    created: int
    updated: int
    total: int


class SyncPricesOut(BaseModel):
    updated: int
    source: str


class ModelOut(ORMModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    external_id: str
    display_name_fa: str | None
    family: str | None
    context_window: int | None
    max_output: int | None
    modalities: list[str]
    supports_tools: bool
    supports_stream: bool
    supports_vision: bool
    supports_audio: bool
    supports_reasoning: bool
    input_price: Decimal | None
    output_price: Decimal | None
    cached_input_price: Decimal | None
    image_price: Decimal | None
    audio_input_price: Decimal | None = None
    audio_output_price: Decimal | None = None
    audio_kind: str | None = None
    # chat model that accepts audio input (no dedicated STT/TTS endpoint)
    audio_chat: bool = False
    #: Persian verdict for speech models (verified/good/weak/none), ``None`` if unknown
    persian: str | None = None

    price_currency: str
    price_source: str | None
    price_synced_at: Any | None
    markup_percent: Decimal
    is_enabled: bool


class ModelCreate(BaseModel):
    """Manual catalog entry (mainly for audio models that a provider omits)."""

    provider_id: uuid.UUID
    external_id: str = Field(min_length=1, max_length=200)
    display_name_fa: str | None = Field(default=None, max_length=200)
    family: str | None = Field(default=None, max_length=80)
    audio_kind: Literal["stt", "tts"] | None = None
    audio_input_price: Decimal | None = Field(default=None, ge=0)
    audio_output_price: Decimal | None = Field(default=None, ge=0)
    input_price: Decimal | None = Field(default=None, ge=0)
    output_price: Decimal | None = Field(default=None, ge=0)
    voices: list[str] | None = None
    is_enabled: bool = True
    #: Operator override for the measured Persian verdict (see app.audio.languages)
    persian: Literal["verified", "good", "weak", "none", "unknown"] | None = None


class ModelUpdate(BaseModel):
    display_name_fa: str | None = Field(default=None, max_length=200)
    is_enabled: bool | None = None
    markup_percent: Decimal | None = Field(default=None, ge=0, le=1000)
    context_window: int | None = Field(default=None, gt=0)
    max_output: int | None = Field(default=None, gt=0)
    supports_tools: bool | None = None
    supports_stream: bool | None = None
    supports_vision: bool | None = None
    supports_audio: bool | None = None
    supports_reasoning: bool | None = None
    #: ``meta.persian`` — a manual Persian verdict that wins over the probe table
    persian: Literal["verified", "good", "weak", "none", "unknown"] | None = None


class ManualPriceIn(BaseModel):
    input_price: Decimal = Field(ge=0)
    output_price: Decimal = Field(ge=0)
    cached_input_price: Decimal | None = Field(default=None, ge=0)
    image_price: Decimal | None = Field(default=None, ge=0)
    audio_input_price: Decimal | None = Field(default=None, ge=0)
    audio_output_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=8)
    note: str | None = Field(default=None, max_length=500)


class ModelProbeIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    max_tokens: int = Field(default=64, ge=1, le=1024)


class ModelProbeOut(BaseModel):
    """One real call through the gateway: proves streaming + pricing end to end."""

    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal
    cost_irr: int
    fx_rate: int
    fallback_used: bool


class PriceHistoryOut(ORMModel):
    id: uuid.UUID
    model_id: uuid.UUID
    effective_from: Any
    input_price: Decimal | None
    output_price: Decimal | None
    cached_input_price: Decimal | None
    image_price: Decimal | None
    audio_input_price: Decimal | None = None
    audio_output_price: Decimal | None = None
    currency: str
    source: str | None
