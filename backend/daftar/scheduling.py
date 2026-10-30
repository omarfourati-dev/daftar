"""Scheduling rules shared by availability, appointments, series and online booking (sections 11.1, 15).

- **Grid**: starts every ``slot_minutes`` from the beginning of each opening window of the weekday; an appointment
  must fit completely into one window (not across the lunch break), never on a closing day.
- **No double bookings**: an appointment blocks its practitioner (or the one "no practitioner" calendar) and its
  patient; ``cancelled`` and ``no_show`` free the slot. The API checks first (:func:`find_conflicts`) and answers
  409 ``appointment_conflict`` with ``conflicts`` and up to 5 ``suggestions``; the database's EXCLUDE constraints are
  the last line – a race between two requests ends in the same 409 (:func:`write_or_409`).
- All days are Tunis calendar days; "now" comes from the injected clock.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from pydantic import AfterValidator, AwareDatetime
from sqlalchemy import Connection, func, or_, select
from sqlalchemy.exc import IntegrityError

from .clock import TUNIS, at_tunis, iso_tunis, tunis_day_bounds
from .db import constraint_name
from .hours import windows_for
from .problems import ApiError, unprocessable
from .tables import FREEING_STATUSES, PATIENT_OVERLAP, PRACTITIONER_OVERLAP, appointment, patient, practice, practice_closure

#: An appointment may start this long before "now" (the running quarter of an hour is still bookable at the desk).
PAST_GRACE = timedelta(minutes=15)
SUGGESTION_DAYS = 7
SUGGESTION_COUNT = 5
OVERLAP_CONSTRAINTS = (PRACTITIONER_OVERLAP, PATIENT_OVERLAP)


def _whole_minute(value: datetime) -> datetime:
    if value.second or value.microsecond:
        raise ValueError("invalid_time: L'heure doit être une minute pleine (HH:MM).")
    return value


#: API input of an appointment start: ISO-8601 with offset, whole minutes.
StartsAt = Annotated[AwareDatetime, AfterValidator(_whole_minute)]


@dataclass(frozen=True)
class Calendar:
    """What the rules need to know about a practice."""

    practice_id: int
    weekly_hours: dict[str, Any]
    slot_minutes: int
    default_duration_min: int


@dataclass(frozen=True)
class Busy:
    id: int
    practitioner_id: int | None
    patient_id: int
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class Conflict:
    id: int
    starts_at: datetime
    ends_at: datetime
    patient_name: str

    def as_json(self) -> dict[str, Any]:
        return {"id": self.id, "startsAt": iso_tunis(self.starts_at), "endsAt": iso_tunis(self.ends_at),
                "patientName": self.patient_name}


def load_calendar(conn: Connection, practice_id: int) -> Calendar:
    row = conn.execute(
        select(practice.c.weekly_hours, practice.c.slot_minutes, practice.c.default_duration_min).where(
            practice.c.id == practice_id
        )
    ).one()
    return Calendar(practice_id, row.weekly_hours, row.slot_minutes, row.default_duration_min)


def local_day(value: datetime) -> date:
    return value.astimezone(TUNIS).date()


def closed_days(conn: Connection, practice_id: int, first: date, last: date) -> set[date]:
    """Every day in ``[first, last]`` covered by a closure of the practice."""
    rows = conn.execute(
        select(practice_closure.c.starts_on, practice_closure.c.ends_on).where(
            practice_closure.c.practice_id == practice_id,
            practice_closure.c.ends_on >= first,
            practice_closure.c.starts_on <= last,
        )
    ).all()
    days: set[date] = set()
    for starts_on, ends_on in rows:
        day = max(starts_on, first)
        while day <= min(ends_on, last):
            days.add(day)
            day += timedelta(days=1)
    return days


def fits_opening_hours(weekly_hours: dict[str, Any], starts_at: datetime, ends_at: datetime) -> bool:
    """True when ``[starts_at, ends_at)`` lies inside one opening window of its (Tunis) day."""
    start, end = starts_at.astimezone(TUNIS), ends_at.astimezone(TUNIS)
    if start.date() != end.date():
        return False
    return any(a <= start.time() and end.time() <= b for a, b in windows_for(weekly_hours, start.date()))


def grid(cal: Calendar, day: date, duration_min: int) -> list[datetime]:
    """Possible starts of a ``duration_min`` appointment on ``day`` (fitting completely into a window)."""
    starts: list[datetime] = []
    step, length = timedelta(minutes=cal.slot_minutes), timedelta(minutes=duration_min)
    for a, b in windows_for(cal.weekly_hours, day):
        t, close = at_tunis(day, a), at_tunis(day, b)
        while t + length <= close:
            starts.append(t)
            t += step
    return starts


def busy_between(
    conn: Connection, practice_id: int, start: datetime, end: datetime, *, exclude_id: int | None = None
) -> list[Busy]:
    """Blocking appointments of the practice that overlap ``[start, end)``."""
    query = select(
        appointment.c.id, appointment.c.practitioner_id, appointment.c.patient_id, appointment.c.starts_at,
        appointment.c.ends_at,
    ).where(
        appointment.c.practice_id == practice_id,
        appointment.c.status.notin_(FREEING_STATUSES),
        appointment.c.starts_at < end,
        appointment.c.ends_at > start,
    )
    if exclude_id is not None:
        query = query.where(appointment.c.id != exclude_id)
    return [Busy(*row) for row in conn.execute(query).all()]


def find_conflicts(
    conn: Connection,
    practice_id: int,
    *,
    practitioner_id: int | None,
    patient_id: int,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: int | None = None,
) -> list[Conflict]:
    """Blocking appointments that overlap and share the practitioner calendar or the patient."""
    query = (
        select(
            appointment.c.id, appointment.c.starts_at, appointment.c.ends_at,
            (patient.c.first_name + " " + patient.c.last_name).label("patient_name"),
        )
        .select_from(appointment.join(patient, patient.c.id == appointment.c.patient_id))
        .where(
            appointment.c.practice_id == practice_id,
            appointment.c.status.notin_(FREEING_STATUSES),
            appointment.c.starts_at < ends_at,
            appointment.c.ends_at > starts_at,
            or_(
                func.coalesce(appointment.c.practitioner_id, 0) == (practitioner_id or 0),
                appointment.c.patient_id == patient_id,
            ),
        )
        .order_by(appointment.c.starts_at, appointment.c.id)
    )
    if exclude_id is not None:
        query = query.where(appointment.c.id != exclude_id)
    return [Conflict(*row) for row in conn.execute(query).all()]


def free_starts(
    conn: Connection,
    cal: Calendar,
    day: date,
    duration_min: int,
    resources: Sequence[int | None],
    *,
    not_before: datetime,
    patient_id: int | None = None,
    exclude_id: int | None = None,
    closed: set[date] | None = None,
) -> list[tuple[datetime, list[int | None]]]:
    """Starts on ``day`` (≥ ``not_before``) with the practitioners of ``resources`` that are free for the whole
    duration (``None`` = the "no practitioner" calendar); the patient, if given, must be free too."""
    if day in (closed if closed is not None else closed_days(conn, cal.practice_id, day, day)):
        return []
    starts = [t for t in grid(cal, day, duration_min) if t >= not_before]
    if not starts or not resources:
        return []
    first, last = tunis_day_bounds(day)
    busy = busy_between(conn, cal.practice_id, first, last, exclude_id=exclude_id)
    length = timedelta(minutes=duration_min)
    result: list[tuple[datetime, list[int | None]]] = []
    for t in starts:
        overlapping = [b for b in busy if b.starts_at < t + length and b.ends_at > t]
        if patient_id is not None and any(b.patient_id == patient_id for b in overlapping):
            continue
        free = [r for r in resources if not any((b.practitioner_id or 0) == (r or 0) for b in overlapping)]
        if free:
            result.append((t, free))
    return result


def suggestions(
    conn: Connection,
    cal: Calendar,
    *,
    practitioner_id: int | None,
    patient_id: int,
    starts_at: datetime,
    duration_min: int,
    now: datetime,
    exclude_id: int | None = None,
) -> list[datetime]:
    """Up to 5 free starts of the same length and practitioner from ``starts_at`` on, within 7 days."""
    begin = max(starts_at, now)
    until = starts_at + timedelta(days=SUGGESTION_DAYS)
    day, last = local_day(begin), local_day(until)
    closed = closed_days(conn, cal.practice_id, day, last)
    found: list[datetime] = []
    while day <= last and len(found) < SUGGESTION_COUNT:
        for t, _ in free_starts(conn, cal, day, duration_min, [practitioner_id], not_before=begin,
                                patient_id=patient_id, exclude_id=exclude_id, closed=closed):
            if t >= until or len(found) == SUGGESTION_COUNT:
                break
            found.append(t)
        day += timedelta(days=1)
    return found


def check_bookable(conn: Connection, cal: Calendar, starts_at: datetime, ends_at: datetime, now: datetime) -> None:
    """422 ``in_past`` (more than 15 min ago), ``closed`` (closing day) or ``outside_hours``."""
    if starts_at < now - PAST_GRACE:
        raise unprocessable("Ce rendez-vous serait dans le passé.", code="in_past")
    day = local_day(starts_at)
    if closed_days(conn, cal.practice_id, day, day):
        raise unprocessable("Le cabinet est fermé ce jour-là.", code="closed")
    if not fits_opening_hours(cal.weekly_hours, starts_at, ends_at):
        raise unprocessable("Ce créneau est en dehors des horaires d'ouverture.", code="outside_hours")


def conflict_error(conflicts: Sequence[Conflict], proposals: Sequence[datetime]) -> ApiError:
    return ApiError(
        409,
        "Ce créneau est déjà pris.",
        code="appointment_conflict",
        extra={"conflicts": [c.as_json() for c in conflicts], "suggestions": [iso_tunis(t) for t in proposals]},
    )


def write_or_409(
    conn: Connection,
    cal: Calendar,
    statement: Any,
    *,
    practitioner_id: int | None,
    patient_id: int,
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
    exclude_id: int | None = None,
) -> Any:
    """Checks for overlaps, then runs ``statement`` (insert/update of an appointment) in a savepoint.

    An overlap found by the check or – in a race – by the EXCLUDE constraints raises 409 ``appointment_conflict``
    with the conflicting appointments and suggestions."""
    where = {"practitioner_id": practitioner_id, "patient_id": patient_id, "starts_at": starts_at, "ends_at": ends_at,
             "exclude_id": exclude_id}

    def refuse(found: list[Conflict]) -> ApiError:
        proposals = suggestions(conn, cal, practitioner_id=practitioner_id, patient_id=patient_id, starts_at=starts_at,
                                duration_min=int((ends_at - starts_at).total_seconds() // 60), now=now,
                                exclude_id=exclude_id)
        return conflict_error(found, proposals)

    found = find_conflicts(conn, cal.practice_id, **where)
    if found:
        raise refuse(found)
    try:
        with conn.begin_nested():
            return conn.execute(statement)
    except IntegrityError as exc:
        if constraint_name(exc) not in OVERLAP_CONSTRAINTS:
            raise
        # the other request has committed by now (the constraint waited for it) – show what it booked
        raise refuse(find_conflicts(conn, cal.practice_id, **where)) from exc

