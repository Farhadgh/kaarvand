"""Cost accounting maths."""

from __future__ import annotations

from decimal import Decimal

from app.billing.cost import compute_cost_usd, price_model_usage, to_irr


def test_cost_usd_uses_per_token_prices() -> None:
    cost = compute_cost_usd(
        tokens_in=1_000,
        tokens_out=500,
        input_price=Decimal("0.000003"),
        output_price=Decimal("0.000015"),
    )
    assert cost == Decimal("0.01050000")


def test_cached_tokens_are_billed_with_cache_price() -> None:
    cost = compute_cost_usd(
        tokens_in=1_000,
        tokens_out=0,
        input_price=Decimal("0.000003"),
        output_price=Decimal("0"),
        cached_tokens=400,
        cached_input_price=Decimal("0.0000003"),
    )
    # 600 * 3e-6 + 400 * 3e-7 = 0.0018 + 0.00012
    assert cost == Decimal("0.00192000")


def test_irr_conversion_applies_markup_and_fx() -> None:
    assert (
        to_irr(Decimal("1"), markup_percent=Decimal("20"), fx_rate=Decimal("1000000")) == 1_200_000
    )
    assert to_irr(Decimal("0.5"), markup_percent=0, fx_rate=0) == 0


def test_price_model_usage_helper() -> None:
    class FakeModel:
        input_price = Decimal("0.000003")
        output_price = Decimal("0.000015")
        markup_percent = Decimal("10")

    usd, irr = price_model_usage(
        FakeModel(),
        tokens_in=1000,
        tokens_out=1000,
        fx_rate=Decimal("900000"),
    )
    assert usd == Decimal("0.01800000")
    assert irr == int(Decimal("0.018") * Decimal("1.1") * Decimal("900000"))
