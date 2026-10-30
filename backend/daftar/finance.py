"""Money of a practice (section 5 "Geld"): treatments (the plan/acts), payments in instalments, balances.

All amounts are integer millimes. Balance of a patient = Σ treatment.price − Σ payment.amount.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Connection, ColumnElement, func, select
from sqlalchemy.sql import Select

from .schemas import ApiModel, TunisDateTime
from .tables import app_user, patient, payment, treatment


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
