"""Money of a practice (section 5 "Geld"): treatments (the plan/acts), payments in instalments, balances.

All amounts are integer millimes (never floats): prices ``0 … 100 000 DT``, payments ``> 0``.
Balance of a patient = Σ treatment.price − Σ payment.amount (negative when overpaid).

- ``POST /api/patients/{id}/treatments`` → 201 · ``PATCH/DELETE /api/treatments/{id}``
- ``POST /api/patients/{id}/payments`` → 201 · ``GET /api/payments/{id}`` (receipt) · ``DELETE`` (owner)
- ``GET /api/cash?day=`` (default today) · ``GET /api/balances?limit=100`` (only due > 0, largest first)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import Connection, ColumnElement, delete, func, insert, select, update
from sqlalchemy.sql import Select

from .access import OwnerWriter
from .clock import today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, StaffUser, StaffWriter
from .money import Millimes, PositiveMillimes
from .problems import not_found, unprocessable
from .schemas import ApiModel, InstantIn, TunisDateTime
from .tables import PAYMENT_METHODS, app_user, appointment, patient, payment, practice, treatment


class TreatmentOut(ApiModel):
    id: int
    label: str
    tooth: str | None
    price_millimes: int
    performed_on: date | None
    appointment_id: int | None
    created_at: TunisDateTime


class PaymentOut(ApiModel):
    id: int
    patient_id: int
    patient_name: str
    amount_millimes: int
    method: str
    paid_at: TunisDateTime
    appointment_id: int | None
    is_deposit: bool
    note: str
    received_by_name: str | None


def treatment_out(row: Any) -> TreatmentOut:
    return TreatmentOut.model_validate(row, from_attributes=True)


def payment_select() -> Select[Any]:
    return select(
        payment,
        (patient.c.first_name + " " + patient.c.last_name).label("patient_name"),
        app_user.c.name.label("received_by_name"),
    ).select_from(
        payment.join(patient, patient.c.id == payment.c.patient_id).outerjoin(
            app_user, app_user.c.id == payment.c.received_by
        )
    )


def payment_out(row: Any) -> PaymentOut:
    return PaymentOut.model_validate(row, from_attributes=True)


def load_payments(conn: Connection, practice_id: int, *conditions: ColumnElement[bool]) -> list[PaymentOut]:
    query = (
        payment_select()
        .where(payment.c.practice_id == practice_id, *conditions)
        .order_by(payment.c.paid_at.desc(), payment.c.id.desc())
    )
    return [payment_out(row) for row in conn.execute(query)]


def load_treatments(conn: Connection, practice_id: int, patient_id: int) -> list[TreatmentOut]:
    query = (
        select(treatment)
        .where(treatment.c.practice_id == practice_id, treatment.c.patient_id == patient_id)
        .order_by(treatment.c.performed_on.desc().nulls_first(), treatment.c.created_at.desc(), treatment.c.id.desc())
    )
    return [treatment_out(row) for row in conn.execute(query)]


def treatments_total(patient_id: Any) -> Any:
    """Σ treatment prices of a patient (correlated scalar subquery, 0 when none)."""
    return (
        select(func.coalesce(func.sum(treatment.c.price_millimes), 0))
        .where(treatment.c.patient_id == patient_id)
        .scalar_subquery()
    )


def payments_total(patient_id: Any) -> Any:
    """Σ payments of a patient (correlated scalar subquery, 0 when none)."""
    return (
        select(func.coalesce(func.sum(payment.c.amount_millimes), 0))
        .where(payment.c.patient_id == patient_id)
        .scalar_subquery()
    )


# --- balances of all patients ------------------------------------------------------------------------------------

def balances_subquery(practice_id: int) -> Any:
    """``patient_id, due_millimes, last_payment_at`` of every patient of the practice that has treatments."""
    billed = (
        select(treatment.c.patient_id, func.sum(treatment.c.price_millimes).label("total"))
        .where(treatment.c.practice_id == practice_id)
        .group_by(treatment.c.patient_id)
        .subquery()
    )
    paid = (
        select(
            payment.c.patient_id,
            func.sum(payment.c.amount_millimes).label("paid"),
            func.max(payment.c.paid_at).label("last_payment_at"),
        )
        .where(payment.c.practice_id == practice_id)
        .group_by(payment.c.patient_id)
        .subquery()
    )
    return (
        select(
            billed.c.patient_id,
            (billed.c.total - func.coalesce(paid.c.paid, 0)).label("due_millimes"),
            paid.c.last_payment_at,
        )
        .select_from(billed.outerjoin(paid, paid.c.patient_id == billed.c.patient_id))
        .subquery()
    )


def due_total(conn: Connection, practice_id: int) -> int:
    """Σ of all positive balances (what patients still owe the practice)."""
    dues = balances_subquery(practice_id)
    return int(
        conn.execute(select(func.coalesce(func.sum(dues.c.due_millimes), 0)).where(dues.c.due_millimes > 0)).scalar_one()
    )


def payments_of_day(conn: Connection, practice_id: int, day: date) -> list[PaymentOut]:
    start, end = tunis_day_bounds(day)
    return load_payments(conn, practice_id, payment.c.paid_at >= start, payment.c.paid_at < end)


# --- API ---------------------------------------------------------------------------------------------------------

router = APIRouter(tags=["finance"])

Label = Annotated[str, Field(min_length=1, max_length=200)]
Tooth = Annotated[str, Field(max_length=20)]
PaymentNote = Annotated[str, Field(max_length=500)]
PaymentMethod = Literal["cash", "d17", "flouci", "card", "cheque", "transfer", "other"]
#: A payment may be dated a little ahead of the server clock (clock skew), never more.
FUTURE_TOLERANCE = timedelta(minutes=5)


class TreatmentIn(ApiModel):
    label: Label
    tooth: Tooth | None = None
    price_millimes: Millimes
    performed_on: date | None = None
    appointment_id: int | None = None


class TreatmentPatch(ApiModel):
    label: Label | None = None
    tooth: Tooth | None = None
    price_millimes: Millimes | None = None
    performed_on: date | None = None
    appointment_id: int | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self) -> TreatmentPatch:
        for name in ("label", "price_millimes"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


class PaymentIn(ApiModel):
    amount_millimes: PositiveMillimes
    method: PaymentMethod
    paid_at: InstantIn | None = None
    appointment_id: int | None = None
    is_deposit: bool = False
    note: PaymentNote = ""


class ReceiptPractice(ApiModel):
    name: str
    name_ar: str
    address: str
    city: str
    phone: str
    tax_id: str


class ReceiptOut(PaymentOut):
    practice: ReceiptPractice


class CashOut(ApiModel):
    day: date
    total_millimes: int
    by_method: dict[str, int]
    payments: list[PaymentOut]


class BalanceOut(ApiModel):
    patient_id: int
    name: str
    phone: str
    due_millimes: int
    last_payment_at: TunisDateTime | None


def _require_patient(conn: Connection, practice_id: int, patient_id: int) -> None:
    found = conn.execute(
        select(patient.c.id).where(patient.c.id == patient_id, patient.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise not_found()


def _require_own_appointment(conn: Connection, practice_id: int, patient_id: int, appointment_id: int | None) -> None:
    """An appointment linked to a treatment or payment must be one of this patient (same answer for foreign ids)."""
    if appointment_id is None:
        return
    found = conn.execute(
        select(appointment.c.id).where(
            appointment.c.id == appointment_id,
            appointment.c.patient_id == patient_id,
            appointment.c.practice_id == practice_id,
        )
    ).first()
    if found is None:
        raise unprocessable("Ce rendez-vous n'appartient pas à ce patient.", code="appointment_mismatch")


def _treatment_row(conn: Connection, practice_id: int, treatment_id: int) -> Any:
    row = conn.execute(
        select(treatment).where(treatment.c.id == treatment_id, treatment.c.practice_id == practice_id).with_for_update()
    ).first()
    if row is None:
        raise not_found()
    return row


@router.post("/api/patients/{patient_id}/treatments", status_code=201)
def add_treatment(patient_id: int, body: TreatmentIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> TreatmentOut:
    _require_patient(conn, user.pid, patient_id)
    _require_own_appointment(conn, user.pid, patient_id, body.appointment_id)
    values = body.model_dump(by_alias=False)
    values["tooth"] = values["tooth"] or None
    row = conn.execute(
        insert(treatment)
        .values(practice_id=user.pid, patient_id=patient_id, created_at=ctx.clock.now(), **values)
        .returning(treatment)
    ).one()
    return treatment_out(row)


@router.patch("/api/treatments/{treatment_id}")
def patch_treatment(treatment_id: int, body: TreatmentPatch, user: StaffWriter, conn: Conn) -> TreatmentOut:
    row = _treatment_row(conn, user.pid, treatment_id)
    values = body.model_dump(include=body.model_fields_set, by_alias=False)
    if "tooth" in values:
        values["tooth"] = values["tooth"] or None
    if values.get("appointment_id") is not None:
        _require_own_appointment(conn, user.pid, row.patient_id, values["appointment_id"])
    if values:
        row = conn.execute(
            update(treatment).where(treatment.c.id == treatment_id).values(**values).returning(treatment)
        ).one()
    return treatment_out(row)


@router.delete("/api/treatments/{treatment_id}", status_code=204)
def delete_treatment(treatment_id: int, user: StaffWriter, conn: Conn) -> Response:
    result = conn.execute(delete(treatment).where(treatment.c.id == treatment_id, treatment.c.practice_id == user.pid))
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)


@router.post("/api/patients/{patient_id}/payments", status_code=201)
def add_payment(patient_id: int, body: PaymentIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> PaymentOut:
    _require_patient(conn, user.pid, patient_id)
    now = ctx.clock.now()
    if body.paid_at is not None and body.paid_at > now + FUTURE_TOLERANCE:
        raise unprocessable("La date du paiement est dans le futur.", code="paid_at_in_future")
    if body.is_deposit and body.appointment_id is None:
        raise unprocessable("Un acompte doit être lié à un rendez-vous.", code="deposit_needs_appointment")
    _require_own_appointment(conn, user.pid, patient_id, body.appointment_id)
    new_id = conn.execute(
        insert(payment)
        .values(
            practice_id=user.pid,
            patient_id=patient_id,
            amount_millimes=body.amount_millimes,
            method=body.method,
            paid_at=body.paid_at or now,
            appointment_id=body.appointment_id,
            is_deposit=body.is_deposit,
            note=body.note,
            received_by=user.user_id,
            created_at=now,
        )
        .returning(payment.c.id)
    ).scalar_one()
    return load_payments(conn, user.pid, payment.c.id == new_id)[0]


@router.get("/api/payments/{payment_id}")
def receipt(payment_id: int, user: StaffUser, conn: Conn) -> ReceiptOut:
    found = load_payments(conn, user.pid, payment.c.id == payment_id)
    if not found:
        raise not_found()
    p = conn.execute(
        select(practice.c.name, practice.c.name_ar, practice.c.address, practice.c.city, practice.c.phone, practice.c.tax_id)
        .where(practice.c.id == user.pid)
    ).one()
    return ReceiptOut(**found[0].model_dump(by_alias=False), practice=ReceiptPractice.model_validate(p, from_attributes=True))


@router.delete("/api/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: int, user: OwnerWriter, conn: Conn) -> Response:
    result = conn.execute(delete(payment).where(payment.c.id == payment_id, payment.c.practice_id == user.pid))
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)


@router.get("/api/cash")
def cash(user: StaffUser, ctx: Ctx, conn: Conn, day: date | None = None) -> CashOut:
    day = day or today_tunis(ctx.clock)
    payments = payments_of_day(conn, user.pid, day)
    by_method = dict.fromkeys(PAYMENT_METHODS, 0)
    for p in payments:
        by_method[p.method] += p.amount_millimes
    return CashOut(day=day, total_millimes=sum(by_method.values()), by_method=by_method, payments=payments)


@router.get("/api/balances")
def balances(user: StaffUser, conn: Conn, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[BalanceOut]:
    dues = balances_subquery(user.pid)
    rows = conn.execute(
        select(
            patient.c.id,
            (patient.c.first_name + " " + patient.c.last_name).label("name"),
            patient.c.phone,
            dues.c.due_millimes,
            dues.c.last_payment_at,
        )
        .select_from(dues.join(patient, patient.c.id == dues.c.patient_id))
        .where(dues.c.due_millimes > 0)
        .order_by(dues.c.due_millimes.desc(), patient.c.id)
        .limit(limit)
    ).all()
    return [
        BalanceOut(
            patient_id=r.id, name=r.name, phone=r.phone, due_millimes=int(r.due_millimes), last_payment_at=r.last_payment_at
        )
        for r in rows
    ]
