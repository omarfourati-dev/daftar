"""Waiting room (section 5, backlog D1): tickets of the day, the public screen and the patient's ticket page.

Staff (reading: every role; changing: staff of a practice that is not suspended):
- ``GET /api/queue?day=`` (default today in Tunis) → ``[QueueEntry]``: active ones (waiting, called, in_treatment) by
  ticket, then the finished ones (done, left)
- ``POST /api/queue {patientId? | name + phone?}`` → 201 – the next ticket number of the day (race-free: one
  transaction-scoped advisory lock per practice); a patient has at most one active ticket a day (409 ``already_in_queue``).
  A patient with an appointment today (scheduled/confirmed, not linked yet – the earliest) has arrived for it: the
  ticket is linked and the appointment becomes ``arrived`` (code review M4, like "Arrivé" in the agenda)
- ``POST /api/queue/{id}/status {status}`` → QueueEntry; a linked appointment follows (waiting/called → arrived,
  in_treatment, done) as long as it is arrived, in treatment or done
- ``DELETE /api/queue/{id}`` → 204

``position`` (only for waiting, 1-based), ``peopleAhead`` = waiting before me + called ones, ``estimatedWaitMin`` =
peopleAhead × the practice's default duration (whole minutes).

Public, rate-limited per IP, **never names, phone numbers or alerts** (only ticket numbers):
- ``GET /api/public/display/{displayToken}`` → ``{practiceName, called: [ticketNo] (called/in treatment, newest
  call first, max 3), next: [ticketNo] (max 5), waiting}``
- ``GET /api/public/ticket/{ticketToken}`` → ``{practiceName, practicePhone, ticketNo, status, position, peopleAhead,
  estimatedWaitMin, day}``

:func:`add_to_queue` is used by the appointments module (status ``arrived``).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Response
from pydantic import Field
from sqlalchemy import Connection, Row, and_, delete, desc, exists, func, insert, or_, select, text, update

from .clock import today_tunis, tunis_day_bounds
from .deps import ClientIp, Conn, Ctx, StaffUser, StaffWriter
from .phone import OptionalPhone
from .problems import conflict, not_found, unprocessable
from .schemas import ApiModel, TunisDateTime
from .tables import appointment, patient, practice, queue_entry

router = APIRouter(prefix="/api/queue", tags=["queue"])
public_router = APIRouter(prefix="/api/public", tags=["public"])

QueueStatus = Literal["waiting", "called", "in_treatment", "done", "left"]
ACTIVE = ("waiting", "called", "in_treatment")
#: Public screen/ticket requests per IP and 10 minutes (a screen polls every 10 s, a ticket page every 20 s; a
#: practice's Wi-Fi shares one IP).
PUBLIC_LIMIT = 1200
PUBLIC_WINDOW = timedelta(minutes=10)
#: First key of the advisory lock that serializes ticket numbers per practice.
_LOCK_NAMESPACE = 0x51554555  # "QUEU"
#: queue status → status of a linked appointment (``left`` changes nothing).
MIRROR = {"waiting": "arrived", "called": "arrived", "in_treatment": "in_treatment", "done": "done"}
MIRRORED_APPOINTMENT_STATUSES = ("arrived", "in_treatment", "done")
#: An appointment is due this long before its start (“Patient suivant”, section 16.2).
DUE_BEFORE = timedelta(minutes=5)


class QueueEntryOut(ApiModel):
    id: int
    ticket_no: int
    name: str
    phone: str | None
    patient_id: int | None
    appointment_id: int | None
    appointment_at: TunisDateTime | None
    status: QueueStatus
    arrived_at: TunisDateTime
    called_at: TunisDateTime | None
    done_at: TunisDateTime | None
    ticket_token: str
    position: int | None
    people_ahead: int
    estimated_wait_min: int
    #: Medical warning of the linked patient – internal only, never on public pages.
    alerts: str


class QueueIn(ApiModel):
    patient_id: int | None = None
    name: Annotated[str, Field(max_length=120)] = ""
    phone: OptionalPhone = None


class StatusIn(ApiModel):
    status: QueueStatus


class DisplayOut(ApiModel):
    practice_name: str
    called: list[int]
    next: list[int]
    waiting: int


class TicketOut(ApiModel):
    practice_name: str
    practice_phone: str
    ticket_no: int
    status: QueueStatus
    position: int | None
    people_ahead: int
    estimated_wait_min: int
    day: date


# --- the day's queue ----------------------------------------------------------------------------------------------


def _day_rows(conn: Connection, practice_id: int, day: date) -> list[Row[Any]]:
    return list(
        conn.execute(
            select(
                queue_entry,
                appointment.c.starts_at.label("appointment_at"),
                func.coalesce(patient.c.alerts, "").label("alerts"),
            )
            .select_from(
                queue_entry.outerjoin(appointment, appointment.c.id == queue_entry.c.appointment_id).outerjoin(
                    patient, patient.c.id == queue_entry.c.patient_id
                )
            )
            .where(queue_entry.c.practice_id == practice_id, queue_entry.c.day == day)
            .order_by(queue_entry.c.ticket_no)
        ).all()
    )


def _waits(rows: list[Row[Any]], minutes_each: int) -> dict[int, tuple[int | None, int, int]]:
    """ticket id → (position, peopleAhead, estimatedWaitMin) for a day ordered by ticket number."""
    called = sum(1 for r in rows if r.status == "called")
    result: dict[int, tuple[int | None, int, int]] = {}
    position = 0
    for r in rows:
        if r.status == "waiting":
            position += 1
            ahead = position - 1 + called
            result[r.id] = (position, ahead, ahead * minutes_each)
        else:
            result[r.id] = (None, 0, 0)
    return result


def _default_minutes(conn: Connection, practice_id: int) -> int:
    return conn.execute(select(practice.c.default_duration_min).where(practice.c.id == practice_id)).scalar_one()


def day_entries(conn: Connection, practice_id: int, day: date) -> list[QueueEntryOut]:
    rows = _day_rows(conn, practice_id, day)
    waits = _waits(rows, _default_minutes(conn, practice_id))
    out = [
        QueueEntryOut(
            **{k: getattr(r, k) for k in QueueEntryOut.model_fields if k not in ("position", "people_ahead", "estimated_wait_min")},
            position=waits[r.id][0],
            people_ahead=waits[r.id][1],
            estimated_wait_min=waits[r.id][2],
        )
        for r in rows
    ]
    return sorted(out, key=lambda e: (e.status not in ACTIVE, e.ticket_no))


def entry_out(conn: Connection, practice_id: int, entry_id: int) -> QueueEntryOut:
    day = conn.execute(
        select(queue_entry.c.day).where(queue_entry.c.id == entry_id, queue_entry.c.practice_id == practice_id)
    ).scalar()
    if day is None:
        raise not_found()
    return next(e for e in day_entries(conn, practice_id, day) if e.id == entry_id)


def next_ticket_no(conn: Connection, practice_id: int, day: date) -> int:
    """The next free ticket number of the day (call it while holding :func:`lock_queue`)."""
    return conn.execute(
        select(func.coalesce(func.max(queue_entry.c.ticket_no), 0) + 1).where(
            queue_entry.c.practice_id == practice_id, queue_entry.c.day == day
        )
    ).scalar_one()


def lock_queue(conn: Connection, practice_id: int) -> None:
    """Serializes changes to a practice's queue until the transaction ends: ticket numbers (two clicks at once →
    1 and 2) and calling the next person (two calls at once never call the same one)."""
    conn.execute(text("SELECT pg_advisory_xact_lock(CAST(:ns AS integer), CAST(:key AS integer))"), {"ns": _LOCK_NAMESPACE, "key": practice_id % 2_147_483_647})


def add_to_queue(
    conn: Connection,
    practice_id: int,
    *,
    now: datetime,
    day: date,
    name: str,
    phone: str | None,
    patient_id: int | None,
    appointment_id: int | None = None,
) -> int:
    """Inserts a waiting ticket with the next number of ``day``; returns its id."""
    lock_queue(conn, practice_id)
    number = next_ticket_no(conn, practice_id, day)
    return conn.execute(
        insert(queue_entry)
        .values(
            practice_id=practice_id, day=day, ticket_no=number, patient_id=patient_id, appointment_id=appointment_id,
            name=name, phone=phone, status="waiting", arrived_at=now,
        )
        .returning(queue_entry.c.id)
    ).scalar_one()


def in_waiting_room(practice_id: int, day: date) -> Any:
    """SQL condition on ``appointment``: its patient is in the waiting room of ``day`` – an active ticket linked to
    it, or an active ticket of the patient linked to no appointment."""
    return exists().where(
        queue_entry.c.practice_id == practice_id,
        queue_entry.c.day == day,
        queue_entry.c.status.in_(ACTIVE),
        or_(
            queue_entry.c.appointment_id == appointment.c.id,
            and_(queue_entry.c.appointment_id.is_(None), queue_entry.c.patient_id == appointment.c.patient_id),
        ),
    )


def left_the_waiting_room(practice_id: int, day: date) -> Any:
    """SQL condition on ``appointment``: its ticket of ``day`` says the patient left (code review N3)."""
    return exists().where(
        queue_entry.c.practice_id == practice_id,
        queue_entry.c.day == day,
        queue_entry.c.status == "left",
        queue_entry.c.appointment_id == appointment.c.id,
    )


def _todays_appointment(conn: Connection, practice_id: int, patient_id: int, day: date) -> int | None:
    """The patient's earliest scheduled/confirmed appointment of ``day`` that has no ticket yet."""
    start, end = tunis_day_bounds(day)
    ticketed = select(queue_entry.c.appointment_id).where(
        queue_entry.c.practice_id == practice_id, queue_entry.c.appointment_id.is_not(None)
    )
    return conn.execute(
        select(appointment.c.id)
        .where(
            appointment.c.practice_id == practice_id,
            appointment.c.patient_id == patient_id,
            appointment.c.starts_at >= start,
            appointment.c.starts_at < end,
            appointment.c.status.in_(("scheduled", "confirmed")),
            appointment.c.id.not_in(ticketed),
        )
        .order_by(appointment.c.starts_at, appointment.c.id)
        .limit(1)
    ).scalar()


def status_values(status: str, now: datetime, called_at: datetime | None) -> dict[str, Any]:
    """Column values for a new queue status: call time, end time (also used by appointments)."""
    if status == "waiting":
        return {"status": status, "called_at": None, "done_at": None}
    if status == "called":
        return {"status": status, "called_at": now, "done_at": None}
    if status == "in_treatment":
        return {"status": status, "called_at": called_at or now, "done_at": None}
    return {"status": status, "called_at": called_at, "done_at": now}


# --- staff endpoints ----------------------------------------------------------------------------------------------


@router.get("")
def list_queue(user: StaffUser, ctx: Ctx, conn: Conn, day: date | None = None) -> list[QueueEntryOut]:
    return day_entries(conn, user.pid, day or today_tunis(ctx.clock))


@router.post("", status_code=201)
def take_ticket(body: QueueIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> QueueEntryOut:
    day = today_tunis(ctx.clock)
    name, phone = body.name, body.phone
    appointment_id = None
    if body.patient_id is not None:
        pat = conn.execute(
            select(patient.c.first_name, patient.c.last_name, patient.c.phone).where(
                patient.c.id == body.patient_id, patient.c.practice_id == user.pid
            )
        ).first()
        if pat is None:
            raise not_found()
        active = conn.execute(
            select(queue_entry.c.id).where(
                queue_entry.c.practice_id == user.pid,
                queue_entry.c.day == day,
                queue_entry.c.patient_id == body.patient_id,
                queue_entry.c.status.in_(ACTIVE),
            )
        ).first()
        if active is not None:
            raise conflict("Ce patient a déjà un ticket en cours aujourd'hui.", code="already_in_queue")
        name = name or f"{pat.first_name} {pat.last_name}"
        phone = phone or pat.phone
        appointment_id = _todays_appointment(conn, user.pid, body.patient_id, day)
    if not name:
        raise unprocessable("Indiquez un patient ou un nom.", code="name_required")
    entry_id = add_to_queue(
        conn, user.pid, now=ctx.clock.now(), day=day, name=name, phone=phone, patient_id=body.patient_id,
        appointment_id=appointment_id,
    )
    if appointment_id is not None:
        conn.execute(update(appointment).where(appointment.c.id == appointment_id).values(status="arrived"))
    return entry_out(conn, user.pid, entry_id)


def set_queue_status(conn: Connection, practice_id: int, entry_id: int, status: str, now: datetime) -> None:
    """Changes a ticket's status (404 if not of the practice); a linked appointment follows (:data:`MIRROR`)."""
    row = conn.execute(
        select(queue_entry.c.called_at, queue_entry.c.appointment_id).where(
            queue_entry.c.id == entry_id, queue_entry.c.practice_id == practice_id
        )
    ).first()
    if row is None:
        raise not_found()
    conn.execute(update(queue_entry).where(queue_entry.c.id == entry_id).values(**status_values(status, now, row.called_at)))
    if row.appointment_id is not None and status in MIRROR:
        conn.execute(
            update(appointment)
            .where(
                appointment.c.id == row.appointment_id,
                appointment.c.practice_id == practice_id,
                appointment.c.status.in_(MIRRORED_APPOINTMENT_STATUSES),
            )
            .values(status=MIRROR[status])
        )


def next_in_line(
    conn: Connection, practice_id: int, day: date, now: datetime, practitioner_id: int | None = None
) -> list[tuple[int, Literal["appointment", "waiting_list"]]]:
    """The waiting tickets in calling order (section 16.2) as ``(entry id, reason)``.

    First the patients of due appointments (start ≤ now + 5 min, not finished) who are waiting – by appointment time;
    then everybody else by ticket number (early appointment patients count like everybody else). With a
    practitioner: their appointments (and those without practitioner) and every ticket not linked to another
    practitioner's appointment.
    """
    start, end = tunis_day_bounds(day)
    waiting = conn.execute(
        select(queue_entry.c.id, queue_entry.c.patient_id, queue_entry.c.appointment_id,
               appointment.c.practitioner_id.label("doctor"))
        .select_from(queue_entry.outerjoin(appointment, appointment.c.id == queue_entry.c.appointment_id))
        .where(queue_entry.c.practice_id == practice_id, queue_entry.c.day == day, queue_entry.c.status == "waiting")
        .order_by(queue_entry.c.ticket_no)
    ).all()
    due = select(appointment.c.id, appointment.c.patient_id).where(
        appointment.c.practice_id == practice_id,
        appointment.c.starts_at >= start,
        appointment.c.starts_at < end,
        appointment.c.starts_at <= now + DUE_BEFORE,
        appointment.c.status.in_(("scheduled", "confirmed", "arrived")),
    )
    if practitioner_id is not None:
        waiting = [w for w in waiting if w.appointment_id is None or w.doctor in (None, practitioner_id)]
        due = due.where(or_(appointment.c.practitioner_id == practitioner_id, appointment.c.practitioner_id.is_(None)))
    line: list[tuple[int, Literal["appointment", "waiting_list"]]] = []
    taken: set[int] = set()
    for appt in conn.execute(due.order_by(appointment.c.starts_at, appointment.c.id)).all():
        for w in waiting:
            mine = w.appointment_id == appt.id or (w.appointment_id is None and w.patient_id == appt.patient_id)
            if mine and w.id not in taken:
                line.append((w.id, "appointment"))
                taken.add(w.id)
                break
    line.extend((w.id, "waiting_list") for w in waiting if w.id not in taken)
    return line


@router.post("/{entry_id}/status")
def change_status(entry_id: int, body: StatusIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> QueueEntryOut:
    set_queue_status(conn, user.pid, entry_id, body.status, ctx.clock.now())
    return entry_out(conn, user.pid, entry_id)


@router.delete("/{entry_id}", status_code=204)
def delete_ticket(entry_id: int, user: StaffWriter, conn: Conn) -> Response:
    result = conn.execute(delete(queue_entry).where(queue_entry.c.id == entry_id, queue_entry.c.practice_id == user.pid))
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)


# --- public pages ---------------------------------------------------------------------------------------------------


def _limit(ctx: Any, ip: str) -> None:
    ctx.limiter("public-queue", PUBLIC_LIMIT, PUBLIC_WINDOW).enforce(ip)


@public_router.get("/display/{display_token}")
def display(display_token: str, ctx: Ctx, conn: Conn, ip: ClientIp) -> DisplayOut:
    _limit(ctx, ip)
    found = conn.execute(select(practice.c.id, practice.c.name).where(practice.c.display_token == display_token)).first()
    if found is None:
        raise not_found()
    day = today_tunis(ctx.clock)
    where = (queue_entry.c.practice_id == found.id, queue_entry.c.day == day)
    called = conn.execute(
        select(queue_entry.c.ticket_no)
        .where(*where, queue_entry.c.status.in_(("called", "in_treatment")))
        .order_by(desc(queue_entry.c.called_at).nulls_last(), queue_entry.c.ticket_no.desc())
        .limit(3)
    ).scalars().all()
    waiting = conn.execute(
        select(queue_entry.c.ticket_no).where(*where, queue_entry.c.status == "waiting").order_by(queue_entry.c.ticket_no)
    ).scalars().all()
    return DisplayOut(practice_name=found.name, called=list(called), next=list(waiting[:5]), waiting=len(waiting))


@public_router.get("/ticket/{ticket_token}")
def ticket(ticket_token: str, ctx: Ctx, conn: Conn, ip: ClientIp) -> TicketOut:
    _limit(ctx, ip)
    found = conn.execute(
        select(queue_entry.c.id, queue_entry.c.practice_id, queue_entry.c.day, practice.c.name, practice.c.phone,
               practice.c.default_duration_min)
        .select_from(queue_entry.join(practice, practice.c.id == queue_entry.c.practice_id))
        .where(queue_entry.c.ticket_token == ticket_token)
    ).first()
    if found is None:
        raise not_found()
    rows = _day_rows(conn, found.practice_id, found.day)
    mine = next(r for r in rows if r.id == found.id)
    position, ahead, wait = _waits(rows, found.default_duration_min)[found.id]
    return TicketOut(
        practice_name=found.name, practice_phone=found.phone, ticket_no=mine.ticket_no, status=mine.status,
        position=position, people_ahead=ahead, estimated_wait_min=wait, day=found.day,
    )
