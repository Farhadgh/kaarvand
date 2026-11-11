"""Cron parser / matcher / next-run (dependency free)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.runtime.cron import CronError, cron_matches, next_run, next_run_utc, parse_cron

TEHRAN = ZoneInfo("Asia/Tehran")


def local(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TEHRAN)


def test_parses_steps_ranges_and_lists() -> None:
    spec = parse_cron("*/15 8-10 * * *")
    assert spec.minutes == frozenset({0, 15, 30, 45})
    assert spec.hours == frozenset({8, 9, 10})

    spec = parse_cron("0 0 1,15 jan-mar *")
    assert spec.days == frozenset({1, 15})
    assert spec.months == frozenset({1, 2, 3})
    assert spec.days_restricted is True


def test_open_slash_expands_to_upper_bound() -> None:
    assert parse_cron("5/20 * * * *").minutes == frozenset({5, 25, 45})


def test_rejects_invalid_expressions() -> None:
    with pytest.raises(CronError):
        parse_cron("* * * *")
    with pytest.raises(CronError):
        parse_cron("60 * * * *")
    with pytest.raises(CronError):
        parse_cron("*/0 * * * *")
    with pytest.raises(CronError):
        parse_cron("5-1 * * * *")
    with pytest.raises(CronError):
        parse_cron("a * * * *")
    with pytest.raises(CronError):
        parse_cron("1,,2 * * * *")


def test_accepts_weekday_and_month_names() -> None:
    spec = parse_cron("0 8 * * sat")
    assert spec.weekdays == frozenset({6})
    assert parse_cron("0 8 * * mon-fri").weekdays == frozenset({1, 2, 3, 4, 5})


def test_matches_minute_hour_day() -> None:
    assert cron_matches("0 8 * * *", local(2026, 11, 9, 8, 0))
    assert not cron_matches("0 8 * * *", local(2026, 11, 9, 8, 1))
    assert not cron_matches("0 8 * * *", local(2026, 11, 9, 9, 0))


def test_saturday_is_weekday_six() -> None:
    # 2026-11-07 is a Saturday — the Iranian working week starts here
    assert cron_matches("0 9 * * 6", local(2026, 11, 7, 9, 0))
    assert not cron_matches("0 9 * * 6", local(2026, 11, 8, 9, 0))


def test_day_of_month_or_weekday_follows_posix() -> None:
    expression = "0 12 1 * mon"  # first of month OR any Monday
    assert cron_matches(expression, local(2026, 11, 1, 12, 0))  # Sunday the 1st
    assert cron_matches(expression, local(2026, 11, 9, 12, 0))  # Monday the 9th
    assert not cron_matches(expression, local(2026, 11, 3, 12, 0))  # Tuesday


def test_next_run_is_utc_and_strictly_after() -> None:
    nxt = next_run("0 8 * * *", local(2026, 11, 9, 9, 0))
    assert nxt is not None
    assert nxt.tzinfo is not None
    assert nxt.astimezone(TEHRAN) == local(2026, 11, 10, 8, 0)
    assert nxt.astimezone(UTC).hour == 4  # 08:00 Tehran == 04:30 UTC

    later_same_day = next_run("30 22 * * *", local(2026, 11, 9, 9, 0))
    assert later_same_day is not None
    assert later_same_day.astimezone(TEHRAN) == local(2026, 11, 9, 22, 30)


def test_next_run_of_impossible_date_is_none() -> None:
    assert next_run("0 0 31 2 *", local(2026, 11, 9, 0, 0), max_days=60) is None


def test_next_run_utc_wrapper_never_raises() -> None:
    assert next_run_utc("bad cron") is None
    assert next_run_utc(None) is None
    assert next_run_utc("* * * * *", now=local(2026, 11, 9, 9, 0)) is not None


def test_next_run_in_a_far_timezone_is_consistent() -> None:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)  # 15:30 Tehran
    nxt = next_run("0 16 * * *", now, timezone="Asia/Tehran")
    assert nxt is not None
    assert nxt.astimezone(TEHRAN).hour == 16
    assert nxt.astimezone(TEHRAN).day == 9
