"""Public (customer) catalog schemas.

Deliberately free of provider identity: no provider id/name, no ``base_url``,
no USD prices and no price source. The customer sees a Persian name, what the
model can do and the Toman price they will be charged.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CatalogModelOut(BaseModel):
    id: uuid.UUID
    name: str
    family: str | None = None
    context_window: int | None = None
    max_output: int | None = None
    modalities: list[str] = []
    capabilities: list[str] = []
    audio_kind: str | None = None
    audio_chat: bool = False
    persian: str | None = None
    #: ``per_1m_tokens`` | ``per_minute`` (STT) | ``per_1k_chars`` (TTS)
    billing_unit: str = "per_1m_tokens"
    price_input_toman: int | None = None
    price_output_toman: int | None = None
    price_image_toman: int | None = None
    price_audio_minute_toman: int | None = None
    price_audio_1k_chars_toman: int | None = None
    #: at least one price is known (otherwise the model is "قیمت‌نشده")
    price_known: bool = False


class CatalogSummaryOut(BaseModel):
    total: int
    with_tools: int
    with_vision: int
    audio: int
    fx_configured: bool
