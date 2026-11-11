"""Dependency-free 5-field cron parser, matcher and "next run" calculator.

Fields: ``minute hour day-of-month month day-of-week``

Supported syntax per field: ``*``, ``*/step``, ``a``, ``a-b``, ``a-b/step``,
``a/step`` and comma separated lists. Weekday ``0`` is Sunday (POSIX), and
``sun..sat`` / ``jan..dec`` names are accepted.

Day-of-month and day-of-week follow POSIX: when **both** are restricted the
task fires if **either** matches; when one of them is ``*`` only the other one
decides. Everything is evaluated in the organization timezone (Asia/Tehran).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FIELD_RANGES: tuple[tuple[int, int], ...] = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
WEEKDAY_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
MONTH_NAMES = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
MAX_SEARCH_DAYS = 400


class CronError(ValueError):
    """Raised for an invalid cron expression."""


@dataclass(frozen=True)
class CronSpec:
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]
    days_restricted: bool
    weekdays_restricted: bool


def _parse_value(token: str, low: int, high: int, index: int) -> int:
    names = {4: WEEKDAY_NAMES, 3: MONTH_NAMES}.get(index, {})
    text = token.strip().lower()
    if text in names:
        return names[text]
    try:
        value = int(text)
    except ValueError as exc:
        raise CronError(f"cron field {index + 1}: '{token}' is not a number") from exc
    if value < low or value > high:
        raise CronError(f"cron field {index + 1}: {value} outside {low}-{high}")
    return value


def _parse_field(raw: str, index: int) -> tuple[frozenset[int], bool]:
    low, high = FIELD_RANGES[index]
    text = raw.strip()
    if not text:
        raise CronError(f"cron field {index + 1} is empty")

    values: set[int] = set()
    restricted = False
    for chunk in text.split(","):
        piece = chunk.strip()
        if not piece:
            raise CronError(f"cron field {index + 1} has an empty item")
        step = 1
        if "/" in piece:
            base, _, step_text = piece.partition("/")
            try:
                step = int(step_text)
            except ValueError as exc:
                raise CronError(f"cron field {index + 1}: bad step '{piece}'") from exc
            if step <= 0:
                raise CronError(f"cron field {index + 1}: step must be positive")
            piece = base.strip()

        if piece == "*":
            start, end = low, high
        elif "-" in piece.lstrip("-"):
            start_text, _, end_text = piece.partition("-")
            start = _parse_value(start_text, low, high, index)
            end = _parse_value(end_text, low, high, index)
            if start > end:
                raise CronError(f"cron field {index + 1}: range start after end")
        else:
            start = _parse_value(piece, low, high, index)
            end = start if step == 1 else high

        if piece != "*" or step != 1:
            restricted = True
        values.update(range(start, end + 1, step))

    return frozenset(values), restricted


def parse_cron(expression: str) -> CronSpec:
    parts = (expression or "").split()
    if len(parts) != 5:
        raise CronError("cron must have 5 fields: minute hour day month weekday")
    minutes, _ = _parse_field(parts[0], 0)
    hours, _ = _parse_field(parts[1], 1)
    days, days_restricted = _parse_field(parts[2], 2)
    months, _ = _parse_field(parts[3], 3)
    weekdays, weekdays_restricted = _parse_field(parts[4], 4)
    return CronSpec(minutes, hours, days, months, weekdays, days_restricted, weekdays_restricted)


def weekdays_of(moment: datetime) -> int:
    """POSIX weekday: Sunday=0 … Saturday=6."""
    return (moment.weekday() + 1) % 7


def _day_matches(spec: CronSpec, day: date) -> bool:
    if day.month not in spec.months:
        return False
    dom = day.day in spec.days
    dow = weekdays_of(datetime.combine(day, time(0, 0))) in spec.weekdays
    if spec.days_restricted and spec.weekdays_restricted:
        return dom or dow
    if spec.days_restricted:
        return dom
    if spec.weekdays_restricted:
        return dow
    return True


def cron_matches(expression: str | CronSpec, moment: datetime) -> bool:
    """True when ``moment`` (already in the target timezone) hits the schedule."""
    spec = parse_cron(expression) if isinstance(expression, str) else expression
    if moment.minute not in spec.minutes or moment.hour not in spec.hours:
        return False
    return _day_matches(spec, moment.date())


def next_run(
    expression: str | CronSpec,
    after: datetime,
    *,
    timezone: str = "Asia/Tehran",
    max_days: int = MAX_SEARCH_DAYS,
) -> datetime | None:
    """First matching minute strictly after ``after`` (returned in UTC)."""
    spec = parse_cron(expression) if isinstance(expression, str) else expression
    tz = ZoneInfo(timezone)
    start = after.astimezone(tz).replace(second=0, microsecond=0) + timedelta(minutes=1)
    hours = sorted(spec.hours)
    minutes = sorted(spec.minutes)

    for offset in range(max_days):
        day = start.date() + timedelta(days=offset)
        if not _day_matches(spec, day):
            continue
        for hour in hours:
            for minute in minutes:
                candidate = datetime.combine(day, time(hour, minute), tzinfo=tz)
                if candidate >= start:
                    return candidate.astimezone(UTC)
    return None


def next_run_utc(
    expression: str | None,
    *,
    now: datetime | None = None,
    timezone: str = "Asia/Tehran",
) -> datetime | None:
    """Safe wrapper for API responses: ``None`` instead of raising."""
    if not expression:
        return None
    try:
        return next_run(expression, now or datetime.now(UTC), timezone=timezone)
    except CronError:
        return None
