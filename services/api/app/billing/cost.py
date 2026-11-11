"""Cost accounting: provider price (USD/token) -> USD -> IRR with markup.

Rounded only at the boundaries so monthly reports stay reproducible.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

USD_QUANT = Decimal("0.00000001")
IRR_QUANT = Decimal("1")


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def compute_cost_usd(
    *,
    tokens_in: int,
    tokens_out: int,
    input_price: Any,
    output_price: Any,
    cached_tokens: int = 0,
    cached_input_price: Any = None,
) -> Decimal:
    cached = max(int(cached_tokens or 0), 0)
    billable_in = max(int(tokens_in or 0) - cached, 0)
    total = _dec(billable_in) * _dec(input_price) + _dec(int(tokens_out or 0)) * _dec(output_price)
    if cached and cached_input_price is not None:
        total += _dec(cached) * _dec(cached_input_price)
    return total.quantize(USD_QUANT, rounding=ROUND_HALF_UP)


def to_irr(
    cost_usd: Any,
    *,
    markup_percent: Any = 0,
    fx_rate: Any = 0,
) -> int:
    multiplier = Decimal(1) + _dec(markup_percent) / Decimal(100)
    amount = _dec(cost_usd) * multiplier * _dec(fx_rate)
    return int(amount.quantize(IRR_QUANT, rounding=ROUND_HALF_UP))


def compute_audio_cost(
    *,
    audio_seconds: int = 0,
    audio_chars: int = 0,
    per_minute_price: Any = None,
    per_1k_chars_price: Any = None,
) -> Decimal:
    """Audio is billed per unit, not per token.

    ``per_minute_price``  -> USD per audio minute (speech-to-text)
    ``per_1k_chars_price`` -> USD per 1000 characters (text-to-speech)
    """
    minutes = Decimal(max(int(audio_seconds or 0), 0)) / Decimal(60)
    kilo_chars = Decimal(max(int(audio_chars or 0), 0)) / Decimal(1000)
    total = minutes * _dec(per_minute_price) + kilo_chars * _dec(per_1k_chars_price)
    return total.quantize(USD_QUANT, rounding=ROUND_HALF_UP)


def price_audio_usage(
    model: Any,
    *,
    audio_seconds: int = 0,
    audio_chars: int = 0,
    fx_rate: Any,
) -> tuple[Decimal, int]:
    """(cost_usd, cost_irr) for one audio call on a ``Model`` row."""
    cost = compute_audio_cost(
        audio_seconds=audio_seconds,
        audio_chars=audio_chars,
        per_minute_price=getattr(model, "audio_input_price", None),
        per_1k_chars_price=getattr(model, "audio_output_price", None),
    )
    return cost, to_irr(
        cost,
        markup_percent=getattr(model, "markup_percent", 0),
        fx_rate=fx_rate,
    )


def price_model_usage(
    model: Any,
    *,
    tokens_in: int,
    tokens_out: int,
    fx_rate: Any,
) -> tuple[Decimal, int]:
    """Convenience: (cost_usd, cost_irr) for one call on a ``Model`` row."""
    cost = compute_cost_usd(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        input_price=getattr(model, "input_price", None),
        output_price=getattr(model, "output_price", None),
    )
    return cost, to_irr(
        cost,
        markup_percent=getattr(model, "markup_percent", 0),
        fx_rate=fx_rate,
    )
