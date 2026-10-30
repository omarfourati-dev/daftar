"""Time: one injectable clock, all business dates in Africa/Tunis (UTC+1, no daylight saving time).

Rules for business code:
- never call ``datetime.now()``/``date.today()`` directly – use ``ctx.clock.now()`` / ``today_tunis(ctx.clock)``;
- store instants as ``TIMESTAMPTZ`` (aware datetimes), days as ``DATE``;
- send instants as ISO-8601 with the Tunis offset (``iso_tunis``), e.g. ``2026-10-30T09:30:00+01:00``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

TUNIS = ZoneInfo("Africa/Tunis")


class Clock(Protocol):
    def now(self) -> datetime:
        """The current instant as an aware datetime (any zone; callers convert)."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A settable clock for tests: ``FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC))``."""

    def __init__(self, at: datetime) -> None:
        self.set(at)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock needs an aware datetime")
        self._at = at

    def advance(self, **delta: float) -> None:
        """``clock.advance(minutes=16)`` – keyword arguments of ``timedelta``."""
        self._at = self._at + timedelta(**delta)


def now_tunis(clock: Clock) -> datetime:
    """The current instant in Tunis local time (aware)."""
    return clock.now().astimezone(TUNIS)


def today_tunis(clock: Clock) -> date:
    """“Today” for every business rule: the calendar date in Tunis."""
    return now_tunis(clock).date()


def tunis_day_bounds(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a Tunis calendar day as aware datetimes – for ``starts_at >= start AND starts_at < end``."""
    start = datetime.combine(day, time.min, tzinfo=TUNIS)
    return start, start + timedelta(days=1)


def at_tunis(day: date, at: time) -> datetime:
    """A wall-clock time on a Tunis day, e.g. ``at_tunis(day, time(9, 30))``."""
    return datetime.combine(day, at, tzinfo=TUNIS)


def iso_tunis(value: datetime) -> str:
    """ISO-8601 with offset in Tunis time, seconds precision: ``2026-10-30T09:30:00+01:00``."""
    if value.tzinfo is None:
        raise ValueError("naive datetime – use aware datetimes everywhere")
    return value.astimezone(TUNIS).isoformat(timespec="seconds")
