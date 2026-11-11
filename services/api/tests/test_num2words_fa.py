"""Persian numbers to words (invoice requirement)."""

from __future__ import annotations

import pytest

from app.core.num2words_fa import amount_to_words_fa, int_to_words_fa, toman_to_words_fa


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, "صفر"),
        (1, "یک"),
        (9, "نه"),
        (10, "ده"),
        (12, "دوازده"),
        (19, "نوزده"),
        (20, "بیست"),
        (21, "بیست و یک"),
        (99, "نود و نه"),
        (100, "یکصد"),
        (101, "یکصد و یک"),
        (999, "نهصد و نود و نه"),
        (1000, "یک هزار"),
        (120000, "یکصد و بیست هزار"),
        (1000000, "یک میلیون"),
        (
            1234567,
            "یک میلیون و دویست و سی و چهار هزار و پانصد و شصت و هفت",
        ),
    ],
)
def test_int_to_words_fa(number: int, expected: str) -> None:
    assert int_to_words_fa(number) == expected


def test_negative_and_units() -> None:
    assert int_to_words_fa(-5) == "منفی پنج"
    assert amount_to_words_fa(120000) == "یکصد و بیست هزار ریال"
    assert toman_to_words_fa(120000) == "یکصد و بیست هزار تومان"


def test_too_large_raises() -> None:
    with pytest.raises(ValueError):
        int_to_words_fa(10**19)
