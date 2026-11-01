"""``/api/patients``: list and search, the patient file, appointments and ledger of a patient (sections 5, 15).

- ``GET /api/patients?q=&limit=50&offset=0`` → ``{items:[PatientSummary], total}``; ``q`` matches first/last name
  (every word, case-insensitive) or – when it only consists of digits and separators – the phone digits.
- ``POST /api/patients`` → 201 Patient · ``GET/PATCH /api/patients/{id}`` · ``DELETE`` (owner) → 204 (cascades).
- ``GET /api/patients/{id}/appointments`` (newest first) · ``GET /api/patients/{id}/ledger``.

Birth: ``birthDate`` is optional (labs need it on specimen labels); when it is set, ``birthYear`` is its year –
another year in the same request is 422 ``birth_year_mismatch``, a date in the future or before 1900 422
``invalid_birth_date``. Patients with a year only stay valid; clearing the date keeps the year.

Reliability: ``noShows`` = no_show, ``attended`` = done, ``cancelled`` = cancelled appointments.
``nextAppointmentAt`` = earliest appointment from now on that is still planned (requested … in_treatment).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import Connection, ColumnElement, and_, delete, func, insert, or_, select, update

from .appointments import AppointmentOut, load_appointments
from .clock import today_tunis
from .deps import Conn, Ctx, OwnerWriter, StaffUser, StaffWriter
from .finance import PaymentOut, TreatmentOut, load_payments, load_treatments, payments_total, treatments_total
from .phone import Phone
from .problems import not_found, unprocessable
from .schemas import ApiModel, Lang, Name, TunisDateTime
from .sterilization import release_patient
from .tables import appointment, patient, payment

router = APIRouter(prefix="/api/patients", tags=["patients"])

#: Statuses of an appointment that still lies ahead (for ``nextAppointmentAt``).
PLANNED_STATUSES = ("requested", "scheduled", "confirmed", "arrived", "in_treatment")
MAX_LIMIT = 200
_PHONE_QUERY = re.compile(r"^[\d\s.\-/()+]+$")

Notes = Annotated[str, Field(max_length=5000)]
Alerts = Annotated[str, Field(max_length=500)]
BirthYear = Annotated[int, Field(ge=1900, le=2100)]


# --- models ----------------------------------------------------------------------------------------------------

class PatientSummary(ApiModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    birth_year: int | None
    birth_date: date | None
    lang: str
    reminder_consent: bool
    no_shows: int
    attended: int
    due_millimes: int
    next_appointment_at: TunisDateTime | None
    has_alerts: bool


class SamePhone(ApiModel):
    id: int
    first_name: str
    last_name: str


class PatientOut(PatientSummary):
    notes: str
    alerts: str
    created_at: TunisDateTime
    cancelled: int
    total_millimes: int
    paid_millimes: int
    same_phone: list[SamePhone]


class PatientPage(ApiModel):
    items: list[PatientSummary]
    total: int


class PatientIn(ApiModel):
    first_name: Name
    last_name: Name
    phone: Phone
    birth_year: BirthYear | None = None
    birth_date: date | None = None
    lang: Lang = "fr"
    reminder_consent: bool = False
    notes: Notes = ""
    alerts: Alerts = ""


#: Fields that may be left out of a PATCH but never set to null.
_REQUIRED = ("first_name", "last_name", "phone", "lang", "reminder_consent", "notes", "alerts")


class PatientPatch(ApiModel):
    first_name: Name | None = None
    last_name: Name | None = None
    phone: Phone | None = None
    birth_year: BirthYear | None = None
    birth_date: date | None = None
    lang: Lang | None = None
    reminder_consent: bool | None = None
    notes: Notes | None = None
    alerts: Alerts | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self) -> PatientPatch:
        for name in _REQUIRED:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


class Ledger(ApiModel):
    treatments: list[TreatmentOut]
    payments: list[PaymentOut]
    total_millimes: int
    paid_millimes: int
    due_millimes: int


# --- queries ---------------------------------------------------------------------------------------------------

def _count(status: str) -> Any:
    return (
        select(func.count())
        .select_from(appointment)
        .where(appointment.c.patient_id == patient.c.id, appointment.c.status == status)
        .scalar_subquery()
    )


def summary_select(now: datetime) -> Any:
    next_at = (
        select(func.min(appointment.c.starts_at))
        .where(
            appointment.c.patient_id == patient.c.id,
            appointment.c.starts_at >= now,
            appointment.c.status.in_(PLANNED_STATUSES),
        )
        .scalar_subquery()
    )
    return select(
        patient,
        _count("no_show").label("no_shows"),
        _count("done").label("attended"),
        _count("cancelled").label("cancelled"),
        treatments_total(patient.c.id).label("total_millimes"),
        payments_total(patient.c.id).label("paid_millimes"),
        next_at.label("next_appointment_at"),
    )


def search_conditions(q: str) -> list[ColumnElement[bool]]:
    """Every word must match the first or last name; a pure phone input matches the phone digits."""
    q = q.strip()
    if not q:
        return []
    if _PHONE_QUERY.fullmatch(q):
        digits = re.sub(r"\D", "", q)
        if digits.startswith("00"):
            digits = digits[2:]
        if digits:
            return [patient.c.phone.contains(digits)]
    return [
        or_(patient.c.first_name.icontains(word, autoescape=True), patient.c.last_name.icontains(word, autoescape=True))
        for word in q.split()
    ]


def _summary_values(row: Any) -> dict[str, Any]:
    total, paid = int(row.total_millimes), int(row.paid_millimes)
    return {
        "id": row.id,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "phone": row.phone,
        "birth_year": row.birth_year,
        "birth_date": row.birth_date,
        "lang": row.lang,
        "reminder_consent": row.reminder_consent,
        "no_shows": row.no_shows,
        "attended": row.attended,
        "due_millimes": total - paid,
        "next_appointment_at": row.next_appointment_at,
        "has_alerts": bool(row.alerts.strip()),
    }


def find_patient(conn: Connection, practice_id: int, patient_id: int, *, lock: bool = False) -> Any:
    """The patient row of this practice or 404 (also for other practices' ids)."""
    query = select(patient).where(patient.c.id == patient_id, patient.c.practice_id == practice_id)
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).first()
    if row is None:
        raise not_found()
    return row


def load_patient(conn: Connection, practice_id: int, patient_id: int, now: datetime) -> PatientOut:
    row = conn.execute(
        summary_select(now).where(patient.c.id == patient_id, patient.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    family = conn.execute(
        select(patient.c.id, patient.c.first_name, patient.c.last_name)
        .where(patient.c.practice_id == practice_id, patient.c.phone == row.phone, patient.c.id != row.id)
        .order_by(patient.c.last_name, patient.c.first_name, patient.c.id)
    ).all()
    return PatientOut(
        **_summary_values(row),
        notes=row.notes,
        alerts=row.alerts,
        created_at=row.created_at,
        cancelled=row.cancelled,
        total_millimes=int(row.total_millimes),
        paid_millimes=int(row.paid_millimes),
        same_phone=[SamePhone(id=f.id, first_name=f.first_name, last_name=f.last_name) for f in family],
    )


def _check_birth_year(ctx: Any, birth_year: int | None) -> None:
    if birth_year is not None and birth_year > today_tunis(ctx.clock).year:
        raise unprocessable("L'année de naissance est dans le futur.", code="invalid_birth_year")


def _mismatch() -> Exception:
    return unprocessable("L'année ne correspond pas à la date de naissance.", code="birth_year_mismatch")


def _birth(ctx: Any, sent: dict[str, Any], current_date: date | None = None) -> dict[str, Any]:
    """The birth fields to store: a sent date sets the year (another sent year is a mismatch); a sent year must agree
    with the date that stays."""
    if sent.get("birth_date") is not None:
        born: date = sent["birth_date"]
        if not date(1900, 1, 1) <= born <= today_tunis(ctx.clock):
            raise unprocessable("Date de naissance invalide.", code="invalid_birth_date")
        if sent.get("birth_year") not in (None, born.year):
            raise _mismatch()
        return {**sent, "birth_year": born.year}
    _check_birth_year(ctx, sent.get("birth_year"))
    stays = current_date if "birth_date" not in sent else None
    if stays is not None and "birth_year" in sent and sent["birth_year"] != stays.year:
        raise _mismatch()
    return sent


# --- endpoints -------------------------------------------------------------------------------------------------

@router.get("")
def list_patients(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientPage:
    where = and_(patient.c.practice_id == user.pid, *search_conditions(q))
    total = conn.execute(select(func.count()).select_from(patient).where(where)).scalar_one()
    rows = conn.execute(
        summary_select(ctx.clock.now())
        .where(where)
        .order_by(patient.c.last_name, patient.c.first_name, patient.c.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return PatientPage(items=[PatientSummary(**_summary_values(r)) for r in rows], total=total)


@router.post("", status_code=201)
def create_patient(body: PatientIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> PatientOut:
    values = _birth(ctx, body.model_dump(by_alias=False))
    new_id = conn.execute(
        insert(patient)
        .values(practice_id=user.pid, created_at=ctx.clock.now(), **values)
        .returning(patient.c.id)
    ).scalar_one()
    return load_patient(conn, user.pid, new_id, ctx.clock.now())


@router.get("/{patient_id}")
def get_patient(patient_id: int, user: StaffUser, ctx: Ctx, conn: Conn) -> PatientOut:
    return load_patient(conn, user.pid, patient_id, ctx.clock.now())


@router.patch("/{patient_id}")
def patch_patient(patient_id: int, body: PatientPatch, user: StaffWriter, ctx: Ctx, conn: Conn) -> PatientOut:
    current = find_patient(conn, user.pid, patient_id, lock=True)
    values = _birth(ctx, body.model_dump(include=body.model_fields_set, by_alias=False), current.birth_date)
    if values:
        conn.execute(
            update(patient).where(patient.c.id == patient_id, patient.c.practice_id == user.pid).values(**values)
        )
    return load_patient(conn, user.pid, patient_id, ctx.clock.now())


@router.delete("/{patient_id}", status_code=204)
def delete_patient(patient_id: int, user: OwnerWriter, conn: Conn) -> Response:
    """Deletes the patient and – through the composite foreign keys – appointments, queue tickets, treatments,
    payments and specimen label prints of the patient. The sterile packs he got stay used (traceability): their use
    keeps his number only."""
    release_patient(conn, user.pid, patient_id)
    result = conn.execute(delete(patient).where(patient.c.id == patient_id, patient.c.practice_id == user.pid))
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)


@router.get("/{patient_id}/appointments")
def patient_appointments(patient_id: int, user: StaffUser, conn: Conn) -> list[AppointmentOut]:
    find_patient(conn, user.pid, patient_id)
    return list(reversed(load_appointments(conn, user.pid, appointment.c.patient_id == patient_id)))


@router.get("/{patient_id}/ledger")
def patient_ledger(patient_id: int, user: StaffUser, conn: Conn) -> Ledger:
    find_patient(conn, user.pid, patient_id)
    treatments = load_treatments(conn, user.pid, patient_id)
    payments = load_payments(conn, user.pid, payment.c.patient_id == patient_id)
    total = sum(t.price_millimes for t in treatments)
    paid = sum(p.amount_millimes for p in payments)
    return Ledger(treatments=treatments, payments=payments, total_millimes=total, paid_millimes=paid, due_millimes=total - paid)
