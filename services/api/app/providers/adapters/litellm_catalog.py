"""Model and price discovery (network side)."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.providers.adapters.chat_common import make_client
from app.providers.adapters.litellm_endpoints import (
    LITELLM_PREFIX,
    build_headers,
    build_query_params,
    models_endpoint,
    parse_models,
    to_decimal,
)
from app.providers.base import ConnectionResult, RemoteModel, RemotePrice
from app.providers.credentials import decrypt_api_key, scrub


async def _get_json(provider: Any, url: str, *, timeout: float) -> dict[str, Any]:
    api_key = decrypt_api_key(provider)
    async with make_client(provider, timeout=timeout) as client:
        response = await client.get(
            url,
            headers=build_headers(provider, api_key),
            params=build_query_params(provider, api_key),
        )
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}


async def list_models(provider: Any, *, timeout: float = 30.0) -> list[RemoteModel]:
    endpoint = models_endpoint(provider)
    if not endpoint:
        return []
    payload = await _get_json(provider, endpoint, timeout=timeout)
    return parse_models(provider, payload)


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


async def fetch_prices(provider: Any, *, timeout: float = 30.0) -> list[RemotePrice]:
    """Provider published prices; falls back to the offline table if installed."""
    endpoint = getattr(provider, "prices_url", None)
    if not endpoint and provider.kind == "openrouter":
        endpoint = models_endpoint(provider)

    if endpoint:
        payload = await _get_json(provider, endpoint, timeout=timeout)
        prices = _prices_from_payload(payload)
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
