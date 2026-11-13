"""Retail pricing: provider USD prices -> what the customer pays in Toman.

Rules
-----
* a model's own ``markup_percent`` wins; when it is ``0`` the platform default
  (``APP_PLATFORM_MARKUP_PERCENT``, 30 %) applies. Billing and the public
  catalog both call :func:`effective_markup_percent`, so the price the customer
  reads is exactly the price that gets charged;
* providers quote USD per token; customers read **Toman per 1,000,000 tokens**
  (the unit every model comparison uses);
* audio is quoted per minute (STT) or per 1,000 characters (TTS).

The wallet stores Rial; one Toman is 10 Rial.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import Settings, get_settings

TOMAN = 10
PER_MILLION = 1_000_000
PER_1K = 1_000
PER_UNIT = 1


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def effective_markup_percent(model: Any, settings: Settings | None = None) -> Decimal:
    """Per model markup if set, otherwise the platform default."""
    own = _dec(getattr(model, "markup_percent", 0))
    if own > 0:
        return own
    return _dec((settings or get_settings()).platform_markup_percent)


def toman_for(
    price_usd: Any,
    *,
    fx_rate: Any,
    markup_percent: Any,
    units: int = PER_MILLION,
) -> int | None:
    """USD per token/unit -> Toman per ``units`` of that unit (rounded)."""
    if price_usd is None:
        return None
    amount = (
        _dec(price_usd)
        * Decimal(units)
        * (Decimal(1) + _dec(markup_percent) / Decimal(100))
        * _dec(fx_rate)
    )
    return int((amount / Decimal(TOMAN)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def retail_prices(
    model: Any,
    *,
    fx_rate: Any,
    settings: Settings | None = None,
) -> dict[str, int | None]:
    """Every customer facing price of one model, in Toman."""
    markup = effective_markup_percent(model, settings)
    return {
        "price_input_toman": toman_for(
            getattr(model, "input_price", None),
            fx_rate=fx_rate,
            markup_percent=markup,
            units=PER_MILLION,
        ),
        "price_output_toman": toman_for(
            getattr(model, "output_price", None),
            fx_rate=fx_rate,
            markup_percent=markup,
            units=PER_MILLION,
        ),
        "price_image_toman": toman_for(
            getattr(model, "image_price", None),
            fx_rate=fx_rate,
            markup_percent=markup,
            units=PER_UNIT,
        ),
        "price_audio_minute_toman": toman_for(
            getattr(model, "audio_input_price", None),
            fx_rate=fx_rate,
            markup_percent=markup,
            units=PER_UNIT,
        ),
        "price_audio_1k_chars_toman": toman_for(
            getattr(model, "audio_output_price", None),
            fx_rate=fx_rate,
            markup_percent=markup,
            units=PER_1K,
        ),
    }
