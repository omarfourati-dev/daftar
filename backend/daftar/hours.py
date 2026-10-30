"""Opening hours: ``weekly_hours`` JSON, ISO weekday ("1" = Monday … "7" = Sunday) → list of ``["HH:MM", "HH:MM"]``.

``{"1": [["08:00", "12:30"], ["14:00", "18:00"]], …, "7": []}`` – a day without windows (or missing) is closed.
The agenda shows the earliest opening to the latest closing of the week (:func:`agenda_range`).
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Annotated, Any

from pydantic import AfterValidator

WEEKDAYS = tuple(str(d) for d in range(1, 8))
MAX_WINDOWS_PER_DAY = 6
_HHMM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

DEFAULT_WEEKLY_HOURS: dict[str, list[list[str]]] = {
    **{d: [["08:00", "12:30"], ["14:00", "18:00"]] for d in WEEKDAYS[:6]},
    "7": [],
}


def _parse(value: str) -> time:
    return time.fromisoformat(value)


def validate_weekly_hours(value: Any) -> dict[str, list[list[str]]]:
    if not isinstance(value, dict):
        raise ValueError("invalid_hours: Horaires invalides.")
    unknown = set(value) - set(WEEKDAYS)
    if unknown:
        raise ValueError("invalid_hours: Jour de semaine inconnu.")
    result: dict[str, list[list[str]]] = {}
    for day in WEEKDAYS:
        windows = value.get(day) or []
        if not isinstance(windows, list) or len(windows) > MAX_WINDOWS_PER_DAY:
            raise ValueError("invalid_hours: Horaires invalides.")
        clean: list[list[str]] = []
        for window in windows:
            if (
                not isinstance(window, list | tuple)
                or len(window) != 2
                or not all(isinstance(v, str) and _HHMM.fullmatch(v) for v in window)
                or window[0] >= window[1]
            ):
                raise ValueError("invalid_hours: Créneau horaire invalide (HH:MM, début avant fin).")
            clean.append([window[0], window[1]])
        clean.sort()
        for before, after in zip(clean, clean[1:], strict=False):
            if after[0] < before[1]:
                raise ValueError("invalid_hours: Les créneaux d'une journée se chevauchent.")
        result[day] = clean
    return result


#: Pydantic type for API input: validates, sorts the windows and fills every weekday.
WeeklyHours = Annotated[dict[str, list[list[str]]], AfterValidator(validate_weekly_hours)]


def windows_for(weekly_hours: dict[str, Any], day: date) -> list[tuple[time, time]]:
    """Opening windows of a calendar day (by its ISO weekday)."""
    return [(_parse(a), _parse(b)) for a, b in weekly_hours.get(str(day.isoweekday()), [])]


def agenda_range(weekly_hours: dict[str, Any]) -> tuple[time, time] | None:
    """Earliest opening and latest closing over the week; None when the practice is never open."""
    windows = [(_parse(a), _parse(b)) for day in WEEKDAYS for a, b in weekly_hours.get(day, [])]
    if not windows:
        return None
    return min(a for a, _ in windows), max(b for _, b in windows)
