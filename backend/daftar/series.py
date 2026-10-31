"""Recurring appointments (backlog B4, section 15) – physiotherapy or psychotherapy courses.

- ``POST /api/appointments/series/preview {patientId, startsAt, durationMin?, serviceId?, practitionerId?, reason,
  notes?, rule: {weekdays: [1..7], count: 1..52}}`` (every staff role) → ``{occurrences: [{startsAt, endsAt,
  conflict: {id, startsAt, endsAt, patientName} | null, closed}]}`` – from the day of ``startsAt`` on, every listed ISO
  weekday at the same Tunis time until ``count`` sessions; ``closed`` = closing day or outside the opening hours.
- ``POST /api/appointments/series {…, skipConflicts}`` → 201 ``{seriesId, created: [Appointment], skipped:
  [{startsAt, reason: 'conflict'|'closed'}]}``. Closed occurrences are always skipped; a conflict without
  ``skipConflicts`` → 409 ``appointment_conflict`` (nothing is created); nothing left → 422 ``series_empty``.
  Every session is checked again by the database (a race skips or refuses that session like a conflict).
  Without ``practitionerId`` in a practice with active practitioners (code review H1): the only one, else the first
  one (practice order) free at every session that is not closed, else per session the first free one.
- ``POST /api/appointments/series/{seriesId}/cancel {from?: 'YYYY-MM-DD'}`` → ``{cancelled: n}`` – cancels the
  requested/scheduled/confirmed sessions from that day on (default today).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import Connection, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import scheduling
from .appointments import (
    OPEN,
    AppointmentOut,
    Reason,
    check_patient,
    check_practitioner,
    check_service,
    load_appointments,
)
from .clock import TUNIS, at_tunis, today_tunis, tunis_day_bounds
from .db import constraint_name
from .deps import Conn, Ctx, Principal, StaffUser, StaffWriter
from .practice_settings import DurationMin
from .problems import not_found, unprocessable
from .scheduling import (
    PAST_GRACE,
    Calendar,
    Conflict,
    StartsAt,
    closed_days,
    conflict_error,
    fits_opening_hours,
    load_calendar,
    local_day,
)
from .schemas import ApiModel, Text, TunisDateTime
from .tables import appointment

router = APIRouter(prefix="/api/appointments/series", tags=["appointments"])

MAX_COUNT = 52
Weekday = Annotated[int, Field(ge=1, le=7)]


class Rule(ApiModel):
    weekdays: Annotated[list[Weekday], Field(min_length=1, max_length=7)]
    count: Annotated[int, Field(ge=1, le=MAX_COUNT)]


class SeriesIn(ApiModel):
    patient_id: int
    starts_at: StartsAt
    duration_min: DurationMin | None = None
    service_id: int | None = None
    practitioner_id: int | None = None
    reason: Reason = ""
    notes: Text = ""
    rule: Rule
    skip_conflicts: bool = False


class ConflictOut(ApiModel):
    id: int
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    patient_name: str


class Occurrence(ApiModel):
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    conflict: ConflictOut | None
    closed: bool


class PreviewOut(ApiModel):
    occurrences: list[Occurrence]


class Skipped(ApiModel):
    starts_at: TunisDateTime
    reason: Literal["conflict", "closed"]


class SeriesOut(ApiModel):
    series_id: str
    created: list[AppointmentOut]
    skipped: list[Skipped]


class CancelIn(ApiModel):
    from_: date | None = Field(default=None, alias="from")


class CancelOut(ApiModel):
    cancelled: int


def occurrence_starts(starts_at: datetime, weekdays: list[int], count: int) -> list[datetime]:
    """``count`` starts on the given ISO weekdays from the day of ``starts_at`` on, at its Tunis wall-clock time."""
    local = starts_at.astimezone(TUNIS)
    wanted, day, starts = set(weekdays), local.date(), []
    while len(starts) < count:
        if day.isoweekday() in wanted:
            starts.append(at_tunis(day, local.time()))
        day += timedelta(days=1)
    return starts


def _doctors(conn: Connection, user: Principal, body: SeriesIn, cal: Calendar, starts: list[datetime], length: timedelta,
             closed: list[bool]) -> list[int | None]:
    """The practitioner of each session (code review H1): the given one; without one in a practice with active
    practitioners the only one, else the first one free at every open session, else per session the first free one
    (the first in practice order when nobody is free – the session then shows its conflict)."""
    if body.practitioner_id is not None:
        return [body.practitioner_id] * len(starts)
    doctors = scheduling.active_practitioners(conn, user.pid)
    if len(doctors) <= 1:
        return [doctors[0] if doctors else None] * len(starts)
    free: list[list[int]] = []
    for start, is_closed in zip(starts, closed, strict=True):
        busy = [] if is_closed else scheduling.busy_between(conn, cal.practice_id, start, start + length)
        free.append([d for d in doctors if scheduling.first_free(busy, [d], start, start + length) is not None])
    steady = next((d for d in doctors if all(d in f for f in free)), None)
    return [steady if steady is not None else (f[0] if f else doctors[0]) for f in free]


def _plan(
    conn: Connection, user: Principal, body: SeriesIn, now: datetime
) -> tuple[Calendar, int, list[Occurrence], list[Conflict], list[int | None]]:
    """Validates the request and checks every occurrence: (calendar, duration, occurrences, conflicts, the
    practitioner of each occurrence)."""
    check_patient(conn, user.pid, body.patient_id)
    check_practitioner(conn, user.pid, body.practitioner_id)
    svc = check_service(conn, user.pid, body.service_id)
    cal = load_calendar(conn, user.pid)
    duration = body.duration_min or (svc.duration_min if svc else cal.default_duration_min)
    if body.starts_at < now - PAST_GRACE:
        raise unprocessable("Ce rendez-vous serait dans le passé.", code="in_past")
    starts = occurrence_starts(body.starts_at, body.rule.weekdays, body.rule.count)
    length = timedelta(minutes=duration)
    closed_on = closed_days(conn, user.pid, local_day(starts[0]), local_day(starts[-1]))
    closed = [local_day(s) in closed_on or not fits_opening_hours(cal.weekly_hours, s, s + length) for s in starts]
    doctors = _doctors(conn, user, body, cal, starts, length, closed)
    occurrences, conflicts = [], []
    for start, is_closed, doctor in zip(starts, closed, doctors, strict=True):
        found = scheduling.find_conflicts(conn, user.pid, practitioner_id=doctor, patient_id=body.patient_id,
                                          starts_at=start, ends_at=start + length)
        first = found[0] if found and not is_closed else None
        if first is not None:
            conflicts.extend(found)
        occurrences.append(Occurrence(
            starts_at=start, ends_at=start + length, closed=is_closed,
            conflict=ConflictOut(id=first.id, starts_at=first.starts_at, ends_at=first.ends_at,
                                 patient_name=first.patient_name) if first else None,
        ))
    return cal, duration, occurrences, conflicts, doctors


@router.post("/preview")
def preview(body: SeriesIn, user: StaffUser, ctx: Ctx, conn: Conn) -> PreviewOut:
    _, _, occurrences, _, _ = _plan(conn, user, body, ctx.clock.now())
    return PreviewOut(occurrences=occurrences)


@router.post("", status_code=201)
def create_series(body: SeriesIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> SeriesOut:
    now = ctx.clock.now()
    _, duration, occurrences, conflicts, doctors = _plan(conn, user, body, now)
    if conflicts and not body.skip_conflicts:
        raise conflict_error(conflicts, [])
    series_id = uuid.uuid4()
    created: list[int] = []
    skipped: list[Skipped] = []
    for occ, doctor in zip(occurrences, doctors, strict=True):
        if occ.closed or occ.conflict is not None:
            skipped.append(Skipped(starts_at=occ.starts_at, reason="closed" if occ.closed else "conflict"))
            continue
        values: dict[str, Any] = {
            "practice_id": user.pid, "patient_id": body.patient_id, "practitioner_id": doctor,
            "service_id": body.service_id, "starts_at": occ.starts_at, "duration_min": duration, "ends_at": occ.ends_at,
            "reason": body.reason, "status": "scheduled", "source": "staff", "notes": body.notes, "series_id": series_id,
            "created_by": user.user_id, "created_at": now,
        }
        try:
            with conn.begin_nested():
                created.append(conn.execute(insert(appointment).values(**values).returning(appointment.c.id)).scalar_one())
        except IntegrityError as exc:  # booked by someone else since the check
            if constraint_name(exc) not in scheduling.OVERLAP_CONSTRAINTS:
                raise
            if not body.skip_conflicts:
                raise conflict_error(
                    scheduling.find_conflicts(conn, user.pid, practitioner_id=doctor,
                                              patient_id=body.patient_id, starts_at=occ.starts_at, ends_at=occ.ends_at),
                    [],
                ) from exc
            skipped.append(Skipped(starts_at=occ.starts_at, reason="conflict"))
    if not created:
        raise unprocessable("Aucune séance ne peut être créée (cabinet fermé ou créneaux pris).", code="series_empty")
    ctx.metrics.appointments_created.labels("series").inc(len(created))
    return SeriesOut(
        series_id=str(series_id),
        created=load_appointments(conn, user.pid, appointment.c.id.in_(created)),
        skipped=skipped,
    )


@router.post("/{series_id}/cancel")
def cancel_series(series_id: str, body: CancelIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> CancelOut:
    try:
        sid = uuid.UUID(series_id)
    except ValueError as exc:
        raise not_found() from exc
    exists = conn.execute(
        select(appointment.c.id).where(appointment.c.practice_id == user.pid, appointment.c.series_id == sid).limit(1)
    ).first()
    if exists is None:
        raise not_found()
    start, _ = tunis_day_bounds(body.from_ or today_tunis(ctx.clock))
    result = conn.execute(
        update(appointment)
        .where(
            appointment.c.practice_id == user.pid,
            appointment.c.series_id == sid,
            appointment.c.starts_at >= start,
            appointment.c.status.in_(OPEN),
        )
        .values(status="cancelled")
    )
    return CancelOut(cancelled=result.rowcount or 0)
