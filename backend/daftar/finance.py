"""Money of a practice (section 5 "Geld"): treatments (the plan/acts), payments in instalments, balances.

All amounts are integer millimes (never floats): prices ``0 … 100 000 DT``, payments ``> 0``.
Balance of a patient = Σ treatment.price − Σ payment.amount (negative when overpaid).

- ``POST /api/patients/{id}/treatments`` → 201 · ``PATCH/DELETE /api/treatments/{id}``
- ``POST /api/patients/{id}/payments`` → 201 · ``GET /api/payments/{id}`` (receipt) · ``DELETE`` (owner)
- ``GET /api/cash?day=`` (default today, with the day's ``closing``) · ``GET /api/balances?limit=100`` (only due > 0,
  largest first) · ``GET /api/balances/summary`` → ``{totalMillimes, patients}`` over **all** positive balances (the
  "Total dû" of the cash book – code review M7: the list is only the largest ones; the dashboard's figure is the same)
- Cash closing (section 16.3): ``POST /api/cash/close {day, countedCashMillimes, note?}`` (staff) compares the counted
  drawer with the day's **cash** payments (``differenceMillimes`` = counted − expected; negative = missing); it can be
  repeated until the owner verifies it with ``POST /api/cash/{day}/verify`` (then 409). ``stale`` = cash payments of the
  day changed after the closing. The owner's dashboard lists closed days that are not verified yet.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import Connection, ColumnElement, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import Select

from .clock import today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, OwnerWriter, StaffUser, StaffWriter
from .money import Millimes, PositiveMillimes
from .problems import ApiError, conflict, not_found, unprocessable
from .schemas import ApiModel, InstantIn, TunisDateTime
from .tables import PAYMENT_METHODS, app_user, appointment, cash_closing, patient, payment, practice, treatment


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


def due_summary(conn: Connection, practice_id: int) -> tuple[int, int]:
    """(Σ of all positive balances, number of patients who owe something)."""
    dues = balances_subquery(practice_id)
    total, count = conn.execute(
        select(func.coalesce(func.sum(dues.c.due_millimes), 0), func.count()).where(dues.c.due_millimes > 0)
    ).one()
    return int(total), int(count)


def due_total(conn: Connection, practice_id: int) -> int:
    """Σ of all positive balances (what patients still owe the practice)."""
    return due_summary(conn, practice_id)[0]


def payments_of_day(conn: Connection, practice_id: int, day: date) -> list[PaymentOut]:
    start, end = tunis_day_bounds(day)
    return load_payments(conn, practice_id, payment.c.paid_at >= start, payment.c.paid_at < end)


# --- cash closing (section 16.3) ---------------------------------------------------------------------------------

class CashClosingOut(ApiModel):
    day: date
    expected_cash_millimes: int
    counted_cash_millimes: int
    difference_millimes: int
    note: str
    closed_by: str | None
    closed_at: TunisDateTime
    verified_by: str | None
    verified_at: TunisDateTime | None
    stale: bool


class UnverifiedDay(ApiModel):
    day: date
    difference_millimes: int
    closed_by: str | None


def cash_in_drawer(conn: Connection, practice_id: int, day: date) -> int:
    """Σ of the day's payments in cash – what the drawer should contain."""
    start, end = tunis_day_bounds(day)
    return int(
        conn.execute(
            select(func.coalesce(func.sum(payment.c.amount_millimes), 0)).where(
                payment.c.practice_id == practice_id, payment.c.method == "cash",
                payment.c.paid_at >= start, payment.c.paid_at < end,
            )
        ).scalar_one()
    )


def _closing_select() -> Any:
    closer, verifier = app_user.alias("closer"), app_user.alias("verifier")
    return select(
        cash_closing, closer.c.name.label("closed_by_name"), verifier.c.name.label("verified_by_name")
    ).select_from(
        cash_closing.outerjoin(closer, closer.c.id == cash_closing.c.closed_by).outerjoin(
            verifier, verifier.c.id == cash_closing.c.verified_by
        )
    )


def load_closing(conn: Connection, practice_id: int, day: date) -> CashClosingOut | None:
    row = conn.execute(
        _closing_select().where(cash_closing.c.practice_id == practice_id, cash_closing.c.day == day)
    ).first()
    if row is None:
        return None
    return CashClosingOut(
        day=row.day,
        expected_cash_millimes=row.expected_cash_millimes,
        counted_cash_millimes=row.counted_cash_millimes,
        difference_millimes=row.counted_cash_millimes - row.expected_cash_millimes,
        note=row.note,
        closed_by=row.closed_by_name,
        closed_at=row.closed_at,
        verified_by=row.verified_by_name,
        verified_at=row.verified_at,
        stale=cash_in_drawer(conn, practice_id, day) != row.expected_cash_millimes,
    )


def unverified_cash_days(conn: Connection, practice_id: int, limit: int = 31) -> list[UnverifiedDay]:
    rows = conn.execute(
        _closing_select()
        .where(cash_closing.c.practice_id == practice_id, cash_closing.c.verified_at.is_(None))
        .order_by(cash_closing.c.day.desc())
        .limit(limit)
    )
    return [
        UnverifiedDay(day=r.day, difference_millimes=r.counted_cash_millimes - r.expected_cash_millimes,
                      closed_by=r.closed_by_name)
        for r in rows
    ]


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
    closing: CashClosingOut | None


class CashCloseIn(ApiModel):
    day: date
    counted_cash_millimes: Millimes
    note: PaymentNote = ""


class BalanceOut(ApiModel):
    patient_id: int
    name: str
    phone: str
    due_millimes: int
    last_payment_at: TunisDateTime | None


class BalancesSummary(ApiModel):
    total_millimes: int
    patients: int


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
    return CashOut(
        day=day, total_millimes=sum(by_method.values()), by_method=by_method, payments=payments,
        closing=load_closing(conn, user.pid, day),
    )


def _verified() -> ApiError:
    return conflict("La caisse de ce jour a déjà été vérifiée.", code="cash_day_verified")


@router.post("/api/cash/close")
def close_cash(body: CashCloseIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> CashClosingOut:
    if body.day > today_tunis(ctx.clock):
        raise unprocessable("On ne peut pas clôturer un jour futur.", code="day_in_future")
    values = {
        "expected_cash_millimes": cash_in_drawer(conn, user.pid, body.day),
        "counted_cash_millimes": body.counted_cash_millimes,
        "note": body.note,
        "closed_by": user.user_id,
        "closed_at": ctx.clock.now(),
    }
    # a verified closing is final – also against a parallel verification (the WHERE of the upsert)
    written = conn.execute(
        pg_insert(cash_closing)
        .values(practice_id=user.pid, day=body.day, **values)
        .on_conflict_do_update(
            index_elements=[cash_closing.c.practice_id, cash_closing.c.day],
            set_=values,
            where=cash_closing.c.verified_at.is_(None),
        )
        .returning(cash_closing.c.day)
    ).first()
    if written is None:
        raise _verified()
    closing = load_closing(conn, user.pid, body.day)
    assert closing is not None
    return closing


@router.post("/api/cash/{day}/verify")
def verify_cash(day: date, user: OwnerWriter, ctx: Ctx, conn: Conn) -> CashClosingOut:
    row = conn.execute(
        select(cash_closing.c.verified_at)
        .where(cash_closing.c.practice_id == user.pid, cash_closing.c.day == day)
        .with_for_update()
    ).first()
    if row is None:
        raise not_found("Cette journée n'est pas clôturée.")
    if row.verified_at is not None:
        raise _verified()
    conn.execute(
        update(cash_closing)
        .where(cash_closing.c.practice_id == user.pid, cash_closing.c.day == day)
        .values(verified_by=user.user_id, verified_at=ctx.clock.now())
    )
    closing = load_closing(conn, user.pid, day)
    assert closing is not None
    return closing


@router.get("/api/balances/summary")
def balances_summary(user: StaffUser, conn: Conn) -> BalancesSummary:
    total, count = due_summary(conn, user.pid)
    return BalancesSummary(total_millimes=total, patients=count)


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
