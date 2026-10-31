"""``/api/appointments`` (sections 5, 11.1, 15; backlog B2, B3, B5). Reading: every staff role; changing: staff of a
practice that is not suspended.

- ``GET ?from=&to=&practitionerId=&status=a,b`` (days in Tunis, default today, at most 62 days) → ``[Appointment]``
  by start · ``GET /overdue`` → today's ``scheduled|confirmed`` appointments that ended more than 15 min ago ·
  ``GET /{id}``
- ``POST {patientId, startsAt, durationMin?, serviceId?, practitionerId?, reason?, notes?, depositRequiredMillimes?,
  status?: scheduled|confirmed}`` → 201 ``{appointment, conflicts: []}``; overlap → 409 ``appointment_conflict``
  ``{conflicts, suggestions}``; 422 ``in_past`` / ``closed`` / ``outside_hours`` / ``invalid_time`` /
  ``practitioner_inactive`` / ``service_inactive``. Without ``durationMin`` the service's duration, else the
  practice default. Without ``practitionerId`` (or ``null``) in a practice with active practitioners: the only one,
  else the first free one (code review H1, :func:`daftar.scheduling.choose_practitioner`) – also when moving or
  reopening an appointment that has none.
- ``PATCH /{id}`` → ``{appointment, conflicts: []}``; time, length, practitioner and patient only change while the
  appointment is requested, scheduled or confirmed (409 ``appointment_locked``) · ``DELETE /{id}`` → 204
- ``POST /{id}/status {status}`` → Appointment (transitions: :data:`TRANSITIONS`, 409 ``invalid_transition``;
  arrival and treatment only on the day – 409 ``not_today`` –, no-show only after the start – 409 ``not_started``).
  Side effects on the waiting room: ``arrived`` adds a ticket for today (or links the patient's open ticket),
  ``in_treatment``/``done`` move it along, ``no_show``/``cancelled`` mark a waiting ticket ``left``, going back to
  ``scheduled``/``confirmed`` removes a waiting ticket.
- ``POST /{id}/reminder`` → Appointment with ``reminderSentAt`` = now

Reusable: :func:`load_appointments` / :func:`load_appointment` build the ``Appointment`` JSON for other modules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import Connection, Row, delete, func, insert, select, update

from .clock import today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, StaffUser, StaffWriter
from .money import Millimes
from .practice_settings import DurationMin
from .problems import conflict, not_found, unprocessable
from .queue import ACTIVE as QUEUE_ACTIVE
from .queue import add_to_queue, status_values
from .scheduling import StartsAt, check_bookable, choose_practitioner, load_calendar, local_day, write_or_409
from .schemas import ApiModel, Lang, Text, TunisDateTime
from .tables import APPOINTMENT_STATUSES, FREEING_STATUSES, appointment, patient, payment, practitioner, queue_entry, service

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

AppointmentStatus = Literal["requested", "scheduled", "confirmed", "arrived", "in_treatment", "done", "no_show", "cancelled"]
#: Statuses in which an appointment can still be moved (time, length, practitioner, patient).
OPEN = ("requested", "scheduled", "confirmed")
TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"scheduled", "confirmed", "cancelled"}),
    "scheduled": frozenset({"confirmed", "arrived", "in_treatment", "done", "no_show", "cancelled"}),
    "confirmed": frozenset({"scheduled", "arrived", "in_treatment", "done", "no_show", "cancelled"}),
    "arrived": frozenset({"scheduled", "confirmed", "in_treatment", "done", "no_show", "cancelled"}),
    "in_treatment": frozenset({"arrived", "done"}),
    "done": frozenset({"in_treatment"}),
    "no_show": frozenset({"scheduled", "confirmed", "arrived"}),
    "cancelled": frozenset({"scheduled", "confirmed"}),
}
OVERDUE_AFTER = timedelta(minutes=15)
MAX_RANGE_DAYS = 62
Reason = Annotated[str, Field(max_length=300)]


# --- output -------------------------------------------------------------------------------------------------------


class PatientBrief(ApiModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    no_shows: int
    #: Medical warning (allergy, anticoagulant …) – shown in red in the appointment dialog.
    alerts: str
    #: The patient's language: texts sent to them (confirmation, refusal, reminder) use it, not the screen's (fixlist 2).
    lang: Lang


class AppointmentOut(ApiModel):
    id: int
    patient: PatientBrief
    practitioner_id: int | None
    practitioner_name: str | None
    service_id: int | None
    service_name: str | None
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    duration_min: int
    reason: str
    status: AppointmentStatus
    source: Literal["staff", "online"]
    notes: str
    patient_note: str
    deposit_required_millimes: int
    deposit_paid_millimes: int
    reminder_sent_at: TunisDateTime | None
    series_id: str | None
    created_at: TunisDateTime


class AppointmentResult(ApiModel):
    appointment: AppointmentOut
    #: Always empty since overlaps are refused with 409 (kept for the shape of section 5).
    conflicts: list[dict[str, Any]] = []


def _query() -> Any:
    other = appointment.alias("other")
    no_shows = (
        select(func.count())
        .where(other.c.patient_id == appointment.c.patient_id, other.c.status == "no_show")
        .scalar_subquery()
    )
    deposit = (
        select(func.coalesce(func.sum(payment.c.amount_millimes), 0))
        .where(payment.c.appointment_id == appointment.c.id, payment.c.is_deposit)
        .scalar_subquery()
    )
    return select(
        appointment,
        patient.c.first_name, patient.c.last_name, patient.c.phone.label("patient_phone"), patient.c.alerts,
        patient.c.lang.label("patient_lang"),
        no_shows.label("no_shows"),
        practitioner.c.name.label("practitioner_name"),
        service.c.name_fr.label("service_name"),
        deposit.label("deposit_paid_millimes"),
    ).select_from(
        appointment.join(patient, patient.c.id == appointment.c.patient_id)
        .outerjoin(practitioner, practitioner.c.id == appointment.c.practitioner_id)
        .outerjoin(service, service.c.id == appointment.c.service_id)
    )


def _out(row: Row[Any]) -> AppointmentOut:
    return AppointmentOut(
        id=row.id,
        patient=PatientBrief(id=row.patient_id, first_name=row.first_name, last_name=row.last_name, phone=row.patient_phone,
                             no_shows=row.no_shows, alerts=row.alerts, lang=row.patient_lang),
        practitioner_id=row.practitioner_id, practitioner_name=row.practitioner_name,
        service_id=row.service_id, service_name=row.service_name,
        starts_at=row.starts_at, ends_at=row.ends_at, duration_min=row.duration_min, reason=row.reason,
        status=row.status, source=row.source, notes=row.notes, patient_note=row.patient_note,
        deposit_required_millimes=row.deposit_required_millimes, deposit_paid_millimes=row.deposit_paid_millimes,
        reminder_sent_at=row.reminder_sent_at, series_id=str(row.series_id) if row.series_id else None,
        created_at=row.created_at,
    )


def load_appointments(conn: Connection, practice_id: int, *where: Any) -> list[AppointmentOut]:
    """``Appointment`` objects of the practice matching ``where``, ordered by start."""
    rows = conn.execute(
        _query().where(appointment.c.practice_id == practice_id, *where).order_by(appointment.c.starts_at, appointment.c.id)
    ).all()
    return [_out(r) for r in rows]


def load_appointment(conn: Connection, practice_id: int, appointment_id: int) -> AppointmentOut:
    found = load_appointments(conn, practice_id, appointment.c.id == appointment_id)
    if not found:
        raise not_found()
    return found[0]


# --- input --------------------------------------------------------------------------------------------------------


class AppointmentIn(ApiModel):
    patient_id: int
    starts_at: StartsAt
    duration_min: DurationMin | None = None
    service_id: int | None = None
    practitioner_id: int | None = None
    reason: Reason = ""
    notes: Text = ""
    deposit_required_millimes: Millimes = 0
    status: Literal["scheduled", "confirmed"] = "scheduled"


class AppointmentPatch(ApiModel):
    patient_id: int | None = None
    starts_at: StartsAt | None = None
    duration_min: DurationMin | None = None
    service_id: int | None = None
    practitioner_id: int | None = None
    reason: Reason | None = None
    notes: Text | None = None
    deposit_required_millimes: Millimes | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> AppointmentPatch:
        for name in self.model_fields_set - {"service_id", "practitioner_id"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


class StatusIn(ApiModel):
    status: AppointmentStatus


def check_patient(conn: Connection, practice_id: int, patient_id: int) -> Row[Any]:
    row = conn.execute(
        select(patient.c.id, patient.c.first_name, patient.c.last_name, patient.c.phone).where(
            patient.c.id == patient_id, patient.c.practice_id == practice_id
        )
    ).first()
    if row is None:
        raise not_found()
    return row


def check_practitioner(conn: Connection, practice_id: int, practitioner_id: int | None) -> None:
    if practitioner_id is None:
        return
    row = conn.execute(
        select(practitioner.c.active).where(practitioner.c.id == practitioner_id, practitioner.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    if not row.active:
        raise unprocessable("Ce praticien n'est plus actif.", code="practitioner_inactive")


def check_service(conn: Connection, practice_id: int, service_id: int | None) -> Row[Any] | None:
    if service_id is None:
        return None
    row = conn.execute(
        select(service.c.duration_min, service.c.name_fr, service.c.active).where(
            service.c.id == service_id, service.c.practice_id == practice_id
        )
    ).first()
    if row is None:
        raise not_found()
    if not row.active:
        raise unprocessable("Cet acte n'est plus proposé.", code="service_inactive")
    return row


def _row(conn: Connection, practice_id: int, appointment_id: int) -> Row[Any]:
    row = conn.execute(
        select(appointment).where(appointment.c.id == appointment_id, appointment.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    return row


def _statuses(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if any(v not in APPOINTMENT_STATUSES for v in values):
        raise unprocessable("Statut inconnu.", code="validation")
    return values


# --- reading ------------------------------------------------------------------------------------------------------


@router.get("")
def list_appointments(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    practitioner_id: Annotated[int | None, Query(alias="practitionerId")] = None,
    status: str | None = None,
) -> list[AppointmentOut]:
    first = from_ or today_tunis(ctx.clock)
    last = to or first
    if last < first:
        raise unprocessable("La fin de la période est avant son début.", code="invalid_range")
    if (last - first).days >= MAX_RANGE_DAYS:
        raise unprocessable(f"Au plus {MAX_RANGE_DAYS} jours à la fois.", code="range_too_long")
    start, _ = tunis_day_bounds(first)
    _, end = tunis_day_bounds(last)
    where = [appointment.c.starts_at >= start, appointment.c.starts_at < end]
    if practitioner_id is not None:
        where.append(appointment.c.practitioner_id == practitioner_id)
    if (wanted := _statuses(status)) is not None:
        where.append(appointment.c.status.in_(wanted))
    return load_appointments(conn, user.pid, *where)


@router.get("/overdue")
def overdue(user: StaffUser, ctx: Ctx, conn: Conn) -> list[AppointmentOut]:
    now = ctx.clock.now()
    start, end = tunis_day_bounds(today_tunis(ctx.clock))
    return load_appointments(
        conn, user.pid,
        appointment.c.starts_at >= start, appointment.c.starts_at < end,
        appointment.c.status.in_(("scheduled", "confirmed")),
        appointment.c.ends_at < now - OVERDUE_AFTER,
    )


@router.get("/{appointment_id}")
def get_appointment(appointment_id: int, user: StaffUser, conn: Conn) -> AppointmentOut:
    return load_appointment(conn, user.pid, appointment_id)


# --- changing -----------------------------------------------------------------------------------------------------


@router.post("", status_code=201)
def create_appointment(body: AppointmentIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> AppointmentResult:
    check_patient(conn, user.pid, body.patient_id)
    check_practitioner(conn, user.pid, body.practitioner_id)
    svc = check_service(conn, user.pid, body.service_id)
    cal = load_calendar(conn, user.pid)
    duration = body.duration_min or (svc.duration_min if svc else cal.default_duration_min)
    ends_at = body.starts_at + timedelta(minutes=duration)
    now = ctx.clock.now()
    check_bookable(conn, cal, body.starts_at, ends_at, now)
    doctor = choose_practitioner(conn, cal, practitioner_id=body.practitioner_id, patient_id=body.patient_id,
                                 starts_at=body.starts_at, ends_at=ends_at, now=now)
    statement = (
        insert(appointment)
        .values(
            practice_id=user.pid, patient_id=body.patient_id, practitioner_id=doctor,
            service_id=body.service_id, starts_at=body.starts_at, duration_min=duration, ends_at=ends_at,
            reason=body.reason, status=body.status, source="staff", notes=body.notes,
            deposit_required_millimes=body.deposit_required_millimes, created_by=user.user_id, created_at=now,
        )
        .returning(appointment.c.id)
    )
    new_id = write_or_409(conn, cal, statement, practitioner_id=doctor, patient_id=body.patient_id,
                          starts_at=body.starts_at, ends_at=ends_at, now=now).scalar_one()
    ctx.metrics.appointments_created.labels("staff").inc()
    return AppointmentResult(appointment=load_appointment(conn, user.pid, new_id))


@router.patch("/{appointment_id}")
def patch_appointment(appointment_id: int, body: AppointmentPatch, user: StaffWriter, ctx: Ctx, conn: Conn) -> AppointmentResult:
    current = _row(conn, user.pid, appointment_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    moving = bool(values.keys() & {"starts_at", "duration_min", "practitioner_id", "patient_id"})
    if moving and current.status not in OPEN:
        raise conflict("Ce rendez-vous est terminé ou annulé : il ne peut plus être déplacé.", code="appointment_locked")
    if "patient_id" in values:
        check_patient(conn, user.pid, values["patient_id"])
    if "practitioner_id" in values and values["practitioner_id"] != current.practitioner_id:
        check_practitioner(conn, user.pid, values["practitioner_id"])
    if "service_id" in values and values["service_id"] != current.service_id:
        check_service(conn, user.pid, values["service_id"])
    starts_at = values.get("starts_at", current.starts_at)
    duration = values.get("duration_min", current.duration_min)
    ends_at = starts_at + timedelta(minutes=duration)
    if values.keys() & {"starts_at", "duration_min"}:
        values["ends_at"] = ends_at
    now = ctx.clock.now()
    if moving:
        cal = load_calendar(conn, user.pid)
        if values.keys() & {"starts_at", "duration_min"}:
            check_bookable(conn, cal, starts_at, ends_at, now)
        patient_id = values.get("patient_id", current.patient_id)
        doctor = choose_practitioner(conn, cal, practitioner_id=values.get("practitioner_id", current.practitioner_id),
                                     patient_id=patient_id, starts_at=starts_at, ends_at=ends_at, now=now,
                                     exclude_id=appointment_id)
        if doctor != current.practitioner_id or "practitioner_id" in values:
            values["practitioner_id"] = doctor
        statement = update(appointment).where(appointment.c.id == appointment_id).values(**values)
        write_or_409(conn, cal, statement, practitioner_id=doctor, patient_id=patient_id, starts_at=starts_at,
                     ends_at=ends_at, now=now, exclude_id=appointment_id)
    elif values:
        conn.execute(update(appointment).where(appointment.c.id == appointment_id).values(**values))
    return AppointmentResult(appointment=load_appointment(conn, user.pid, appointment_id))


@router.delete("/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: int, user: StaffWriter, conn: Conn) -> Response:
    _row(conn, user.pid, appointment_id)
    conn.execute(delete(appointment).where(appointment.c.id == appointment_id))
    return Response(status_code=204)


@router.post("/{appointment_id}/reminder")
def mark_reminder(appointment_id: int, user: StaffWriter, ctx: Ctx, conn: Conn) -> AppointmentOut:
    _row(conn, user.pid, appointment_id)
    conn.execute(update(appointment).where(appointment.c.id == appointment_id).values(reminder_sent_at=ctx.clock.now()))
    return load_appointment(conn, user.pid, appointment_id)


@router.post("/{appointment_id}/status")
def change_status(appointment_id: int, body: StatusIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> AppointmentOut:
    current = _row(conn, user.pid, appointment_id)
    target = body.status
    if target == current.status:
        return load_appointment(conn, user.pid, appointment_id)
    if target not in TRANSITIONS[current.status]:
        raise conflict("Ce changement de statut n'est pas possible.", code="invalid_transition")
    now = ctx.clock.now()
    today, day = today_tunis(ctx.clock), local_day(current.starts_at)
    if (target in ("arrived", "in_treatment") and day != today) or (target == "done" and day > today):
        raise conflict("Ce rendez-vous n'est pas aujourd'hui.", code="not_today")
    if target == "no_show" and current.starts_at > now:
        raise conflict("Le rendez-vous n'a pas encore commencé.", code="not_started")
    statement = update(appointment).where(appointment.c.id == appointment_id).values(status=target)
    if current.status in FREEING_STATUSES and target not in FREEING_STATUSES:  # taking the slot again
        cal = load_calendar(conn, user.pid)
        doctor = choose_practitioner(conn, cal, practitioner_id=current.practitioner_id, patient_id=current.patient_id,
                                     starts_at=current.starts_at, ends_at=current.ends_at, now=now,
                                     exclude_id=appointment_id)
        write_or_409(conn, cal, statement.values(practitioner_id=doctor), practitioner_id=doctor,
                     patient_id=current.patient_id, starts_at=current.starts_at, ends_at=current.ends_at, now=now,
                     exclude_id=appointment_id)
    else:
        conn.execute(statement)
    _follow_in_queue(conn, user.pid, current, target, now, today)
    return load_appointment(conn, user.pid, appointment_id)


def _follow_in_queue(conn: Connection, practice_id: int, appt: Row[Any], target: str, now: datetime, today: date) -> None:
    """Keeps the waiting room in step with the appointment's status."""
    entry = conn.execute(
        select(queue_entry.c.id, queue_entry.c.status, queue_entry.c.called_at).where(
            queue_entry.c.appointment_id == appt.id, queue_entry.c.practice_id == practice_id
        )
    ).first()

    def set_entry(status: str) -> None:
        assert entry is not None
        conn.execute(update(queue_entry).where(queue_entry.c.id == entry.id).values(**status_values(status, now, entry.called_at)))

    if target == "arrived":
        if entry is None:
            _arrive(conn, practice_id, appt, now, today)
        elif entry.status not in ("waiting", "called"):
            set_entry("waiting")
    elif target in ("in_treatment", "done"):
        if entry is not None:
            set_entry(target)
    elif target in FREEING_STATUSES:
        if entry is not None and entry.status in ("waiting", "called"):
            set_entry("left")
    elif entry is not None and entry.status in ("waiting", "called"):  # back to scheduled/confirmed: undo the arrival
        conn.execute(delete(queue_entry).where(queue_entry.c.id == entry.id))


def _arrive(conn: Connection, practice_id: int, appt: Row[Any], now: datetime, today: date) -> None:
    """Links the patient's open ticket of today, or takes a new one."""
    open_ticket = conn.execute(
        select(queue_entry.c.id).where(
            queue_entry.c.practice_id == practice_id,
            queue_entry.c.day == today,
            queue_entry.c.patient_id == appt.patient_id,
            queue_entry.c.appointment_id.is_(None),
            queue_entry.c.status.in_(QUEUE_ACTIVE),
        )
    ).first()
    if open_ticket is not None:
        conn.execute(update(queue_entry).where(queue_entry.c.id == open_ticket.id).values(appointment_id=appt.id))
        return
    pat = check_patient(conn, practice_id, appt.patient_id)
    add_to_queue(conn, practice_id, now=now, day=today, name=f"{pat.first_name} {pat.last_name}", phone=pat.phone,
                 patient_id=appt.patient_id, appointment_id=appt.id)

