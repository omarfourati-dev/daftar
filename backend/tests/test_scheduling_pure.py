"""Scheduling rules without a database (the API tests in tests/termine cover them end to end)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from daftar.scheduling import Busy, first_free

NINE = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)  # Monday 09:00 in Tunis


def busy(practitioner_id: int | None, start: datetime, minutes: int = 30) -> Busy:
    return Busy(id=1, practitioner_id=practitioner_id, patient_id=1, starts_at=start, ends_at=start + timedelta(minutes=minutes))


def test_first_free_takes_the_practice_order() -> None:
    end = NINE + timedelta(minutes=30)
    assert first_free([], [11, 12], NINE, end) == 11
    assert first_free([busy(11, NINE)], [11, 12], NINE, end) == 12
    assert first_free([busy(11, NINE), busy(12, NINE + timedelta(minutes=15))], [11, 12], NINE, end) is None


def test_first_free_ignores_appointments_that_only_touch() -> None:
    end = NINE + timedelta(minutes=30)
    before, after = busy(11, NINE - timedelta(minutes=30)), busy(11, end)
    assert first_free([before, after], [11, 12], NINE, end) == 11
    assert first_free([busy(None, NINE)], [11], NINE, end) == 11  # an old one without practitioner blocks nobody here
