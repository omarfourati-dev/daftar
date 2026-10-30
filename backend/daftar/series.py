"""Recurring appointments (backlog B4, section 15) – physiotherapy or psychotherapy courses.

- ``POST /api/appointments/series/preview {patientId, startsAt, durationMin?, serviceId?, practitionerId?, reason,
  notes?, rule: {weekdays: [1..7], count: 1..52}}`` (every staff role) → ``{occurrences: [{startsAt, endsAt,
  conflict: {id, startsAt, endsAt, patientName} | null, closed}]}`` – from the day of ``startsAt`` on, every listed ISO
  weekday at the same Tunis time until ``count`` sessions; ``closed`` = closing day or outside the opening hours.
- ``POST /api/appointments/series {…, skipConflicts}`` → 201 ``{seriesId, created: [Appointment], skipped:
  [{startsAt, reason: 'conflict'|'closed'}]}``. Closed occurrences are always skipped; a conflict without
  ``skipConflicts`` → 409 ``appointment_conflict`` (nothing is created); nothing left → 422 ``series_empty``.
  Every session is checked again by the database (a race skips or refuses that session like a conflict).
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


def _plan(conn: Connection, user: Principal, body: SeriesIn, now: datetime) -> tuple[Calendar, int, list[Occurrence], list[Conflict]]:
    """Validates the request and checks every occurrence: (calendar, duration, occurrences, conflicts)."""
    check_patient(conn, user.pid, body.patient_id)
    check_practitioner(conn, user.pid, body.practitioner_id)
    svc = check_service(conn, user.pid, body.service_id)
    cal = load_calendar(conn, user.pid)
    duration = body.duration_min or (svc.duration_min if svc else cal.default_duration_min)
    if body.starts_at < now - PAST_GRACE:
        raise unprocessable("Ce rendez-vous serait dans le passé.", code="in_past")
    starts = occurrence_starts(body.starts_at, body.rule.weekdays, body.rule.count)
    length = timedelta(minutes=duration)
    closed = closed_days(conn, user.pid, local_day(starts[0]), local_day(starts[-1]))
    occurrences, conflicts = [], []
    for start in starts:
        found = scheduling.find_conflicts(conn, user.pid, practitioner_id=body.practitioner_id, patient_id=body.patient_id,
                                          starts_at=start, ends_at=start + length)
        is_closed = local_day(start) in closed or not fits_opening_hours(cal.weekly_hours, start, start + length)
        first = found[0] if found and not is_closed else None
        if first is not None:
            conflicts.extend(found)
        occurrences.append(Occurrence(
            starts_at=start, ends_at=start + length, closed=is_closed,
            conflict=ConflictOut(id=first.id, starts_at=first.starts_at, ends_at=first.ends_at,
                                 patient_name=first.patient_name) if first else None,
        ))
    return cal, duration, occurrences, conflicts


@router.post("/preview")
def preview(body: SeriesIn, user: StaffUser, ctx: Ctx, conn: Conn) -> PreviewOut:
    _, _, occurrences, _ = _plan(conn, user, body, ctx.clock.now())
    return PreviewOut(occurrences=occurrences)


@router.post("", status_code=201)
def create_series(body: SeriesIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> SeriesOut:
    now = ctx.clock.now()
    _, duration, occurrences, conflicts = _plan(conn, user, body, now)
    if conflicts and not body.skip_conflicts:
        raise conflict_error(conflicts, [])
    series_id = uuid.uuid4()
    created: list[int] = []
    skipped: list[Skipped] = []
    for occ in occurrences:
        if occ.closed or occ.conflict is not None:
            skipped.append(Skipped(starts_at=occ.starts_at, reason="closed" if occ.closed else "conflict"))
            continue
        values: dict[str, Any] = {
            "practice_id": user.pid, "patient_id": body.patient_id, "practitioner_id": body.practitioner_id,
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
                    scheduling.find_conflicts(conn, user.pid, practitioner_id=body.practitioner_id,
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
