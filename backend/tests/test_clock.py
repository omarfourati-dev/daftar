from datetime import UTC, date, datetime, time

import pytest

from daftar.clock import FixedClock, at_tunis, iso_tunis, now_tunis, today_tunis, tunis_day_bounds


def test_today_is_the_calendar_date_in_tunis() -> None:
    # 23:30 UTC on the 30th is already 00:30 on the 31st in Tunis (UTC+1, no DST)
    assert today_tunis(FixedClock(datetime(2026, 10, 30, 23, 30, tzinfo=UTC))) == date(2026, 10, 31)
    assert today_tunis(FixedClock(datetime(2026, 10, 30, 22, 59, tzinfo=UTC))) == date(2026, 10, 30)


def test_no_daylight_saving_time_in_summer() -> None:
    offset = now_tunis(FixedClock(datetime(2026, 7, 1, 12, 0, tzinfo=UTC))).utcoffset()
    assert offset is not None and offset.total_seconds() == 3600


def test_iso_tunis_has_the_offset() -> None:
    assert iso_tunis(datetime(2026, 10, 30, 8, 30, 15, 123, tzinfo=UTC)) == "2026-10-30T09:30:15+01:00"
    with pytest.raises(ValueError):
        iso_tunis(datetime(2026, 10, 30, 8, 30))


def test_day_bounds_and_wall_clock_times() -> None:
    start, end = tunis_day_bounds(date(2026, 10, 30))
    assert start.astimezone(UTC) == datetime(2026, 10, 29, 23, 0, tzinfo=UTC)
    assert end.astimezone(UTC) == datetime(2026, 10, 30, 23, 0, tzinfo=UTC)
    assert at_tunis(date(2026, 10, 30), time(9, 30)).astimezone(UTC) == datetime(2026, 10, 30, 8, 30, tzinfo=UTC)


def test_fixed_clock_moves_only_when_told() -> None:
    clock = FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC))
    clock.advance(minutes=16)
    assert clock.now() == datetime(2026, 10, 30, 8, 16, tzinfo=UTC)
    with pytest.raises(ValueError):
        clock.set(datetime(2026, 10, 30, 8, 0))
