"""Jalali calendar conversion."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.core.jalali import (
    format_jalali,
    format_jalali_long,
    gregorian_to_jalali,
    jalali_to_gregorian,
    today_jalali,
)


@pytest.mark.parametrize(
    ("gregorian", "jalali"),
    [
        ((1979, 2, 11), (1357, 11, 22)),  # ۲۲ بهمن ۱۳۵۷
        ((2024, 3, 20), (1403, 1, 1)),  # نوروز ۱۴۰۳
        ((2021, 3, 21), (1400, 1, 1)),  # نوروز ۱۴۰۰
        ((2000, 1, 1), (1378, 10, 11)),
        ((2026, 11, 9), (1405, 8, 18)),
    ],
)
def test_known_dates(gregorian: tuple[int, int, int], jalali: tuple[int, int, int]) -> None:
    assert gregorian_to_jalali(*gregorian) == jalali


@pytest.mark.parametrize("iso", ["1900-01-01", "1999-12-31", "2024-02-29", "2026-07-15"])
def test_round_trip(iso: str) -> None:
    value = date.fromisoformat(iso)
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    assert jalali_to_gregorian(jy, jm, jd) == (value.year, value.month, value.day)


def test_format_uses_persian_digits() -> None:
    assert format_jalali(date(2026, 11, 9)) == "۱۴۰۵/۰۸/۱۸"
    assert format_jalali(date(2026, 11, 9), digits="en") == "1405/08/18"
    assert format_jalali_long(date(2024, 3, 20), digits="en") == "1 فروردین 1403"


def test_today_jalali_is_persian() -> None:
    text = today_jalali()
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in text)
    assert any(month in text for month in ("فروردین", "آبان", "اسفند"))


def test_datetime_input_is_accepted() -> None:
    assert format_jalali(datetime(2024, 3, 20, 23, 30), digits="en") == "1403/01/01"
