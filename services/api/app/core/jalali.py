"""Jalali (Solar Hijri) calendar helpers.

The product shows Persian dates everywhere while the database stores UTC. This
module is deliberately dependency free (no jdatetime) and covered by tests.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.text_fa import to_persian_digits

_G_DAYS_IN_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _div(a: int, b: int) -> int:
    return a // b


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400)
    g_day_no += _G_DAYS_IN_MONTH[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1

    j_day_no = g_day_no - 79
    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365

    if j_day_no < 186:
        jm = 1 + _div(j_day_no, 31)
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + _div(j_day_no - 186, 30)
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy2 = jy - 979
    j_day_no = 365 * jy2 + _div(jy2, 33) * 8 + _div((jy2 % 33) + 3, 4)

    for month in range(jm - 1):
        j_day_no += 31 if month < 6 else 30
    j_day_no += jd - 1

    g_day_no = j_day_no + 79
    gy = 1600 + 400 * _div(g_day_no, 146097)
    g_day_no %= 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * _div(g_day_no, 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * _div(g_day_no, 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += _div(g_day_no, 365)
        g_day_no %= 365

    gd = g_day_no + 1
    months = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    gm = 1
    for days in months:
        if gd <= days:
            break
        gd -= days
        gm += 1
    return gy, gm, gd


def jalali_date(value: date | datetime) -> tuple[int, int, int]:
    return gregorian_to_jalali(value.year, value.month, value.day)


def format_jalali(value: date | datetime, *, digits: str = "fa") -> str:
    """``2026-11-09`` -> ``۱۴۰۵/۰۸/۱۸``."""
    jy, jm, jd = jalali_date(value)
    text = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return to_persian_digits(text) if digits == "fa" else text


def format_jalali_long(value: date | datetime, *, digits: str = "fa") -> str:
    months = (
        "فروردین",
        "اردیبهشت",
        "خرداد",
        "تیر",
        "مرداد",
        "شهریور",
        "مهر",
        "آبان",
        "آذر",
        "دی",
        "بهمن",
        "اسفند",
    )
    jy, jm, jd = jalali_date(value)
    text = f"{jd} {months[jm - 1]} {jy}"
    return to_persian_digits(text) if digits == "fa" else text


def now_in(timezone: str = "Asia/Tehran") -> datetime:
    return datetime.now(ZoneInfo(timezone))


def today_jalali(timezone: str = "Asia/Tehran", *, digits: str = "fa") -> str:
    return format_jalali_long(now_in(timezone), digits=digits)
