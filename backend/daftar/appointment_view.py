"""The ``Appointment`` JSON shape (sections 5, 11.2, 15) for every read-only list outside the appointment API itself.

Used by the patient file, reminders and the dashboard::

    load_appointments(conn, user.pid, appointment.c.patient_id == 7, order_by=[appointment.c.starts_at.desc()])

``Appointment {id, patient:{id, firstName, lastName, phone, noShows, alerts}, practitionerId, practitionerName,
serviceId, serviceName, startsAt, endsAt, durationMin, reason, status, source, notes, patientNote,
depositRequiredMillimes, depositPaidMillimes, reminderSentAt, seriesId, createdAt}``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, ColumnElement, func, select
from sqlalchemy.sql import Select

from .schemas import ApiModel, TunisDateTime
from .tables import appointment, patient, payment, practitioner, service


class AppointmentPatient(ApiModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    no_shows: int
    alerts: str


class AppointmentOut(ApiModel):
    id: int
    patient: AppointmentPatient
    practitioner_id: int | None
    practitioner_name: str | None
    service_id: int | None
    service_name: str | None
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    duration_min: int
    reason: str
    status: str
    source: str
    notes: str
    patient_note: str
    deposit_required_millimes: int
    deposit_paid_millimes: int
    reminder_sent_at: TunisDateTime | None
    series_id: UUID | None
    created_at: TunisDateTime


def appointment_select() -> Select[Any]:
    """All columns needed for :class:`AppointmentOut`; add your own ``where`` (always with the practice!)."""
    other = appointment.alias("no_show_appointment")
    no_shows = (
        select(func.count())
        .where(other.c.patient_id == appointment.c.patient_id, other.c.status == "no_show")
        .scalar_subquery()
    )
    deposit_paid = (
        select(func.coalesce(func.sum(payment.c.amount_millimes), 0))
        .where(payment.c.appointment_id == appointment.c.id, payment.c.is_deposit.is_(True))
        .scalar_subquery()
    )
    return select(
        appointment,
        patient.c.first_name.label("patient_first_name"),
        patient.c.last_name.label("patient_last_name"),
        patient.c.phone.label("patient_phone"),
        patient.c.alerts.label("patient_alerts"),
        no_shows.label("patient_no_shows"),
        practitioner.c.name.label("practitioner_name"),
        service.c.name_fr.label("service_name"),
        deposit_paid.label("deposit_paid_millimes"),
    ).select_from(
        appointment.join(patient, patient.c.id == appointment.c.patient_id)
        .outerjoin(practitioner, practitioner.c.id == appointment.c.practitioner_id)
        .outerjoin(service, service.c.id == appointment.c.service_id)
    )


def appointment_out(row: Any) -> AppointmentOut:
    return AppointmentOut(
        id=row.id,
        patient=AppointmentPatient(
            id=row.patient_id,
            first_name=row.patient_first_name,
            last_name=row.patient_last_name,
            phone=row.patient_phone,
            no_shows=row.patient_no_shows,
            alerts=row.patient_alerts,
        ),
        practitioner_id=row.practitioner_id,
        practitioner_name=row.practitioner_name,
        service_id=row.service_id,
        service_name=row.service_name,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        duration_min=row.duration_min,
        reason=row.reason,
        status=row.status,
        source=row.source,
        notes=row.notes,
        patient_note=row.patient_note,
        deposit_required_millimes=row.deposit_required_millimes,
        deposit_paid_millimes=int(row.deposit_paid_millimes),
        reminder_sent_at=row.reminder_sent_at,
        series_id=row.series_id,
        created_at=row.created_at,
    )


def load_appointments(
    conn: Connection,
    practice_id: int,
    *conditions: ColumnElement[bool],
    order_by: Sequence[Any] = (),
    limit: int | None = None,
) -> list[AppointmentOut]:
    query = appointment_select().where(appointment.c.practice_id == practice_id, *conditions)
    query = query.order_by(*order_by, appointment.c.id) if order_by else query.order_by(appointment.c.starts_at, appointment.c.id)
    if limit is not None:
        query = query.limit(limit)
    return [appointment_out(row) for row in conn.execute(query)]
