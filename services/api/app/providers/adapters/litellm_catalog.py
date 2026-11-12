"""Model and price discovery (network side)."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.providers.adapters.chat_common import make_client
from app.providers.adapters.litellm_endpoints import (
    LITELLM_PREFIX,
    _audio_kind_of,
    build_headers,
    build_query_params,
    models_endpoint,
    parse_models,
    to_decimal,
)
from app.providers.base import ConnectionResult, RemoteModel, RemotePrice
from app.providers.credentials import decrypt_api_key, scrub

# OpenRouter only reveals architecture (and pricing) for speech models when the
# list is filtered by output modality, so both lists are fetched on sync.
OPENROUTER_AUDIO_MODALITIES = {"transcription": "stt", "speech": "tts"}


async def _get_json(
    provider: Any,
    url: str,
    *,
    timeout: float,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    api_key = decrypt_api_key(provider)
    query = {**build_query_params(provider, api_key), **(params or {})}
    async with make_client(provider, timeout=timeout) as client:
        response = await client.get(
            url,
            headers=build_headers(provider, api_key),
            # an empty dict would wipe a query string carried by ``url``
            params=query or None,
        )
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}


async def _openrouter_audio_items(provider: Any, *, timeout: float) -> list[dict[str, Any]]:
    """Raw speech-model entries from OpenRouter (best effort, never fatal)."""
    endpoint = models_endpoint(provider)
    if not endpoint:
        return []
    items: list[dict[str, Any]] = []
    for modality in OPENROUTER_AUDIO_MODALITIES:
        try:
            payload = await _get_json(
                provider,
                endpoint,
                timeout=timeout,
                params={"output_modalities": modality},
            )
        except Exception:  # noqa: BLE001 - discovery is best effort
            continue
        items.extend(payload.get("data") or [])
    return items


async def _merge_openrouter_audio(
    provider: Any, models: list[RemoteModel], *, timeout: float
) -> list[RemoteModel]:
    items = await _openrouter_audio_items(provider, timeout=timeout)
    if not items:
        return models
    by_id = {model.external_id: model for model in models}
    for item in items:
        model_id = item.get("id")
        if not model_id:
            continue
        kind = _audio_kind_of(item.get("architecture") or {})
        if kind is None:
            continue
        known = by_id.get(model_id)
        if known is not None:
            known.meta = {**(known.meta or {}), "audio_kind": kind}
            voices = item.get("supported_voices")
            if isinstance(voices, list) and voices:
                known.meta["voices"] = [str(voice) for voice in voices]
            continue
        meta: dict[str, Any] = {
            "audio_kind": kind,
            "pricing": item.get("pricing"),
            "architecture": item.get("architecture"),
        }
        voices = item.get("supported_voices")
        if isinstance(voices, list) and voices:
            meta["voices"] = [str(voice) for voice in voices]
        model = RemoteModel(
            external_id=model_id,
            display_name=item.get("name"),
            meta=meta,
        )

        models.append(model)
        by_id[model_id] = model
    return models


async def list_models(provider: Any, *, timeout: float = 30.0) -> list[RemoteModel]:
    endpoint = models_endpoint(provider)
    if not endpoint:
        return []
    payload = await _get_json(provider, endpoint, timeout=timeout)
    models = parse_models(provider, payload)
    if provider.kind == "openrouter":
        models = await _merge_openrouter_audio(provider, models, timeout=timeout)
    return models


_AUDIO_STEP = Decimal("0.0000000001")


def _audio_prices(
    pricing: dict[str, Any], architecture: dict[str, Any]
) -> tuple[Decimal | None, Decimal | None]:
    """Convert OpenRouter audio pricing to the catalog's units.

    OpenRouter quotes speech-to-text per **audio second** and text-to-speech per
    **character**; the catalog stores STT per minute and TTS per 1000 characters.
    Models that bill per generated second (e.g. music models) cannot be expressed
    in those units, so they keep no audio price and are priced manually.
    """
    outputs = {str(item).lower() for item in architecture.get("output_modalities") or []}
    prompt = to_decimal(pricing.get("prompt") or pricing.get("input"))
    if "transcription" in outputs and prompt is not None:
        return (prompt * 60).quantize(_AUDIO_STEP), None
    if "speech" in outputs and prompt is not None and prompt > 0:
        return None, (prompt * 1000).quantize(_AUDIO_STEP)
    return None, None


def _prices_from_payload(payload: dict[str, Any]) -> list[RemotePrice]:
    prices: list[RemotePrice] = []
    for item in payload.get("data") or payload.get("models") or []:
        model_id = item.get("id") or item.get("name")
        pricing = item.get("pricing") or {}
        if not model_id or not pricing:
            continue
        audio_input, audio_output = _audio_prices(pricing, item.get("architecture") or {})
        prices.append(
            RemotePrice(
                external_id=str(model_id).replace("models/", "", 1),
                input_price=to_decimal(pricing.get("prompt") or pricing.get("input")),
                output_price=to_decimal(pricing.get("completion") or pricing.get("output")),
                cached_input_price=to_decimal(pricing.get("input_cache_read")),
                image_price=to_decimal(pricing.get("image")),
                audio_input_price=audio_input,
                audio_output_price=audio_output,
                source="provider",
            )
        )
    return prices


async def _merge_openrouter_audio_prices(
    provider: Any, prices: list[RemotePrice], *, timeout: float
) -> list[RemotePrice]:
    items = await _openrouter_audio_items(provider, timeout=timeout)
    if not items:
        return prices
    extra = {price.external_id: price for price in _prices_from_payload({"data": items})}
    seen: set[str] = set()
    merged: list[RemotePrice] = []
    for price in prices:
        found = extra.get(price.external_id)
        if found is not None:
            price.audio_input_price = found.audio_input_price
            price.audio_output_price = found.audio_output_price
            seen.add(price.external_id)
        merged.append(price)
    merged.extend(price for key, price in extra.items() if key not in seen)
    return merged


async def fetch_prices(provider: Any, *, timeout: float = 30.0) -> list[RemotePrice]:
    """Provider published prices; falls back to the offline table if installed."""
    endpoint = getattr(provider, "prices_url", None)
    if not endpoint and provider.kind == "openrouter":
        endpoint = models_endpoint(provider)

    if endpoint:
        payload = await _get_json(provider, endpoint, timeout=timeout)
        prices = _prices_from_payload(payload)
        if provider.kind == "openrouter":
            prices = await _merge_openrouter_audio_prices(provider, prices, timeout=timeout)
        if prices:
            return prices
        return litellm_prices(provider)

    # many OpenAI-compatible providers expose pricing on their models endpoint
    models_ep = models_endpoint(provider)
    if models_ep:
        try:
            payload = await _get_json(provider, models_ep, timeout=timeout)
        except Exception:  # noqa: BLE001 - price discovery is best effort
            payload = {}
        prices = _prices_from_payload(payload or {})
        if prices:
            return prices

    return litellm_prices(provider)


def litellm_prices(provider: Any) -> list[RemotePrice]:
    """Offline price table shipped with LiteLLM (used when the provider has none)."""
    try:
        from litellm import model_cost  # lazy: heavy module
    except Exception:  # pragma: no cover - litellm optional at runtime
        return []

    prefix = LITELLM_PREFIX.get(provider.kind, "openai")
    out: list[RemotePrice] = []
    for key, info in model_cost.items():
        if not isinstance(info, dict) or "/" not in key:
            continue
        key_prefix, _, model_id = key.partition("/")
        if key_prefix != prefix:
            continue
        input_cost = info.get("input_cost_per_token")
        output_cost = info.get("output_cost_per_token")
        if input_cost is None and output_cost is None:
            continue
        out.append(
            RemotePrice(
                external_id=model_id,
                input_price=to_decimal(input_cost),
                output_price=to_decimal(output_cost),
                cached_input_price=to_decimal(info.get("cache_read_input_token_cost")),
                source="litellm",
            )
        )
    return out


async def test_connection(provider: Any, *, timeout: float = 20.0) -> ConnectionResult:
    started = time.perf_counter()
    try:
        models = await list_models(provider, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - any transport error means "not ok"
        return ConnectionResult(
            ok=False,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code="provider.connection_failed",
            detail=scrub(provider, str(exc)),
        )
    return ConnectionResult(
        ok=True,
        latency_ms=int((time.perf_counter() - started) * 1000),
        models_seen=len(models),
    )
