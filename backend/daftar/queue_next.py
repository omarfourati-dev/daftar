"""“Patient suivant” for the desk and the doctor (section 16.2).

- ``GET /api/queue/next?practitionerId=`` (every staff role) → ``{entry: QueueEntry|null, reason: 'appointment'|
  'waiting_list'|null, lateAppointments: [Appointment], upcoming: [QueueEntry] (the next 3)}``.
  Rule (:func:`daftar.queue.next_in_line`): the waiting patient of a due appointment (start ≤ now + 5 min) goes first;
  if nobody of a due appointment is there, the first waiting person by ticket number (early appointment patients
  count like everybody else). ``lateAppointments``: today's scheduled/confirmed appointments that started 10 minutes
  ago or more and whose patient is not in the waiting room – marked “en retard”, never set to no-show automatically.
- ``POST /api/queue/call-next {practitionerId?}`` (staff, not suspended) → the QueueEntry just called (``called``).
  Race-free: the per-practice queue lock is held while choosing and calling, so two clicks at once never call the
  same person; nobody waiting → 409 ``queue_empty``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Query
from sqlalchemy import Connection, and_, exists, or_, select

from . import queue
from .appointments import AppointmentOut, load_appointments
from .clock import today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, StaffUser, StaffWriter
from .problems import conflict, not_found
from .queue import ACTIVE, QueueEntryOut
from .schemas import ApiModel
from .tables import appointment, practitioner, queue_entry

router = APIRouter(prefix="/api/queue", tags=["queue"])

#: An appointment patient who is not there this long after the start is “en retard”.
LATE_AFTER = timedelta(minutes=10)
UPCOMING = 3


class NextOut(ApiModel):
    entry: QueueEntryOut | None
    reason: Literal["appointment", "waiting_list"] | None
    late_appointments: list[AppointmentOut]
    upcoming: list[QueueEntryOut]


class CallNextIn(ApiModel):
    practitioner_id: int | None = None


def _check_practitioner(conn: Connection, practice_id: int, practitioner_id: int | None) -> None:
    if practitioner_id is None:
        return
    found = conn.execute(
        select(practitioner.c.id).where(practitioner.c.id == practitioner_id, practitioner.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise not_found()


def late_appointments(
    conn: Connection, practice_id: int, day: date, now: datetime, practitioner_id: int | None
) -> list[AppointmentOut]:
    start, end = tunis_day_bounds(day)
    present = exists().where(
        queue_entry.c.practice_id == practice_id,
        queue_entry.c.day == day,
        queue_entry.c.status.in_(ACTIVE),
        or_(
            queue_entry.c.appointment_id == appointment.c.id,
            and_(queue_entry.c.appointment_id.is_(None), queue_entry.c.patient_id == appointment.c.patient_id),
        ),
    )
    where = [
        appointment.c.starts_at >= start,
        appointment.c.starts_at < end,
        appointment.c.starts_at <= now - LATE_AFTER,
        appointment.c.status.in_(("scheduled", "confirmed")),
        ~present,
    ]
    if practitioner_id is not None:
        where.append(or_(appointment.c.practitioner_id == practitioner_id, appointment.c.practitioner_id.is_(None)))
    return load_appointments(conn, practice_id, *where)


@router.get("/next")
def who_is_next(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    practitioner_id: Annotated[int | None, Query(alias="practitionerId")] = None,
) -> NextOut:
    _check_practitioner(conn, user.pid, practitioner_id)
    day, now = today_tunis(ctx.clock), ctx.clock.now()
    line = queue.next_in_line(conn, user.pid, day, now, practitioner_id)
    entries = {e.id: e for e in queue.day_entries(conn, user.pid, day)}
    return NextOut(
        entry=entries[line[0][0]] if line else None,
        reason=line[0][1] if line else None,
        late_appointments=late_appointments(conn, user.pid, day, now, practitioner_id),
        upcoming=[entries[entry_id] for entry_id, _ in line[1 : 1 + UPCOMING]],
    )


@router.post("/call-next")
def call_next(
    user: StaffWriter,
    ctx: Ctx,
    conn: Conn,
    body: Annotated[CallNextIn | None, Body()] = None,
) -> QueueEntryOut:
    practitioner_id = body.practitioner_id if body else None
    _check_practitioner(conn, user.pid, practitioner_id)
    queue.lock_queue(conn, user.pid)  # held until commit: a second call waits and then sees this one as called
    day, now = today_tunis(ctx.clock), ctx.clock.now()
    line = queue.next_in_line(conn, user.pid, day, now, practitioner_id)
    if not line:
        raise conflict("Personne n'attend.", code="queue_empty")
    entry_id = line[0][0]
    queue.set_queue_status(conn, user.pid, entry_id, "called", now)
    return queue.entry_out(conn, user.pid, entry_id)
