"""When a hygiene task is due (spec stock-hygiène 5.1) – rules without a database."""

from datetime import date, timedelta

import pytest

from daftar.catalog import SPECIALTIES
from daftar.hygiene_rules import (
    EQUIPMENT_KINDS,
    FREQUENCIES,
    Rhythm,
    is_due,
    last_due,
    next_due,
    occurrences,
    open_weekday,
    starter_plan,
)

MONDAY = date(2026, 10, 26)
OPEN_WEEKDAYS = {1, 2, 3, 4, 5, 6}


def open_day(day: date) -> bool:
    return day.isoweekday() in OPEN_WEEKDAYS and day != date(2026, 11, 7)  # a Saturday closure


def test_daily_tasks_are_due_on_opening_days_only() -> None:
    r = Rhythm("daily", starts_on=MONDAY)
    assert [is_due(r, MONDAY + timedelta(days=n), open_day) for n in range(7)] == [True] * 6 + [False]
    assert not is_due(r, MONDAY - timedelta(days=1), open_day)  # before the start
    assert not is_due(r, date(2026, 11, 7), open_day)  # closure


def test_weekly_monthly_yearly_and_every_n_days() -> None:
    weekly = Rhythm("weekly", starts_on=MONDAY, weekday=3)
    assert [d.isoformat() for d in occurrences(weekly, MONDAY, MONDAY + timedelta(days=14), open_day)] == [
        "2026-10-28", "2026-11-04"]
    monthly = Rhythm("monthly", starts_on=date(2026, 1, 31))
    assert [d.isoformat() for d in occurrences(monthly, date(2026, 1, 1), date(2026, 4, 30), open_day)] == [
        "2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]  # the last day of shorter months
    yearly = Rhythm("yearly", starts_on=date(2024, 2, 29))
    assert is_due(yearly, date(2026, 2, 28), open_day) and is_due(yearly, date(2028, 2, 29), open_day)
    assert not is_due(yearly, date(2028, 2, 28), open_day)
    every = Rhythm("every_n_days", starts_on=MONDAY, interval_days=10)
    assert [d.isoformat() for d in occurrences(every, MONDAY, MONDAY + timedelta(days=25), open_day)] == [
        "2026-10-26", "2026-11-05", "2026-11-16"]  # by the calendar; Sunday 15.11. moves to Monday


def test_a_due_date_on_a_closed_day_moves_to_the_next_opening_day() -> None:
    """Review N1: a monthly check due on a Sunday is due on Monday – done that Monday, it is on time."""
    sunday_closed = lambda day: day.isoweekday() != 7  # noqa: E731
    monthly = Rhythm("monthly", starts_on=date(2026, 10, 15))
    assert last_due(monthly, date(2026, 11, 15), sunday_closed) == date(2026, 10, 15)  # Sunday: not due yet
    assert last_due(monthly, date(2026, 11, 16), sunday_closed) == date(2026, 11, 16)
    assert next_due(monthly, date(2026, 11, 1), sunday_closed) == date(2026, 11, 16)
    weekly = Rhythm("weekly", starts_on=date(2026, 10, 1), weekday=6)  # Saturday, in a practice open Monday–Friday
    weekdays_only = lambda day: day.isoweekday() <= 5  # noqa: E731
    assert [d.isoformat() for d in occurrences(weekly, date(2026, 10, 26), date(2026, 11, 9), weekdays_only)] == [
        "2026-10-26", "2026-11-02", "2026-11-09"]  # each Saturday on the Monday after
    holiday = lambda day: not date(2026, 8, 1) <= day <= date(2026, 8, 23) and day.isoweekday() != 7  # noqa: E731
    mondays = Rhythm("weekly", starts_on=date(2026, 7, 1), weekday=1)
    assert [d.isoformat() for d in occurrences(mondays, date(2026, 7, 27), date(2026, 8, 31), holiday)] == [
        "2026-07-27", "2026-08-24", "2026-08-31"]  # three Mondays of the holiday: one test on the first day back
    assert is_due(monthly, date(2026, 11, 15), sunday_closed)  # the rhythm's own date, before it moves
    never_open = lambda day: False  # noqa: E731
    assert occurrences(monthly, date(2026, 11, 1), date(2026, 11, 30), never_open) == [date(2026, 11, 15)]


def test_the_start_plan_puts_a_weekly_task_on_an_opening_day() -> None:
    assert open_weekday(6, {1, 2, 3, 4, 5, 6}) == 6
    assert open_weekday(6, {1, 2, 3, 4, 5}) == 5  # Saturday closed: Friday
    assert open_weekday(1, {2, 3, 4, 5, 6}) == 2  # Monday closed: the next day of the week
    assert open_weekday(3, set()) == 3


def test_last_due_is_the_current_occurrence() -> None:
    weekly = Rhythm("weekly", starts_on=MONDAY, weekday=1)
    assert last_due(weekly, date(2026, 10, 30), open_day) == MONDAY  # Monday's test is still open on Friday
    assert last_due(weekly, date(2026, 11, 2), open_day) == date(2026, 11, 2)  # the next Monday replaces it
    daily = Rhythm("daily", starts_on=MONDAY)
    assert last_due(daily, date(2026, 11, 1), open_day) == date(2026, 10, 31)  # Sunday: Saturday's
    assert last_due(Rhythm("yearly", starts_on=date(2026, 12, 1)), date(2026, 11, 1), open_day) is None
    assert last_due(Rhythm("yearly", starts_on=date(2025, 11, 4)), date(2026, 11, 1), open_day) == date(2025, 11, 4)


def test_rhythm_needs_its_details() -> None:
    with pytest.raises(ValueError):
        Rhythm("weekly", starts_on=MONDAY)
    with pytest.raises(ValueError):
        Rhythm("every_n_days", starts_on=MONDAY, interval_days=1)
    with pytest.raises(ValueError):
        Rhythm("daily", starts_on=MONDAY, weekday=2)


def test_starter_plans_per_specialty() -> None:
    dentist = starter_plan("dentiste")
    titles = {t.title_fr for t in dentist.tasks}
    assert {"Purge des conduits du fauteuil", "Nettoyage de l’aspiration", "Test Bowie-Dick / Hélix de l’autoclave",
            "Maintenance de l’autoclave", "Contrôle de radioprotection"} <= titles
    for specialty in SPECIALTIES:
        plan = starter_plan(specialty)
        equipment = {e.key for e in plan.equipment}
        assert plan.tasks, specialty
        for e in plan.equipment:
            assert e.kind in EQUIPMENT_KINDS and e.name_fr and e.name_ar
        for t in plan.tasks:
            assert t.frequency in FREQUENCIES and t.title_fr and t.title_ar
            assert t.equipment is None or t.equipment in equipment
            Rhythm(t.frequency, starts_on=MONDAY, weekday=t.weekday, interval_days=t.interval_days)
