"""``GET /api/reminders?day=`` (default tomorrow): appointments of a day with a ready-made reminder (section 5).

Each item: ``{appointment, patientLang, reminderConsent, phoneDigits, message}``. ``message`` is the practice's
template in the patient's language with ``{patient} {date} {time} {practice} {phone}`` replaced (date
``dd/mm/yyyy``, time ``HH:MM`` in Tunis). The web app opens ``wa.me/<phoneDigits>`` or ``sms:`` with it; nothing is
sent from the server. Left out: cancelled, no-show and online requests that are not confirmed yet.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy import Connection, func, select

from .appointment_view import AppointmentOut, load_appointments
from .clock import TUNIS, today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, StaffUser
from .phone import phone_digits
from .schemas import ApiModel
from .tables import appointment, patient, practice

router = APIRouter(prefix="/api/reminders", tags=["reminders"])

#: Appointments that get no reminder.
SKIPPED_STATUSES = ("cancelled", "no_show", "requested")
PLACEHOLDERS = ("patient", "date", "time", "practice", "phone")
_PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")


class ReminderOut(ApiModel):
    appointment: AppointmentOut
    patient_lang: str
    reminder_consent: bool
    phone_digits: str
    message: str


def render_message(template: str, values: Mapping[str, str]) -> str:
    """Replaces only the known placeholders, in one pass (no ``str.format`` – templates are user input)."""
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def reminder_conditions(day: date) -> list[Any]:
    start, end = tunis_day_bounds(day)
    return [appointment.c.starts_at >= start, appointment.c.starts_at < end, appointment.c.status.not_in(SKIPPED_STATUSES)]


def pending_count(conn: Connection, practice_id: int, day: date) -> int:
    """Appointments of ``day`` whose patient agreed to reminders and that were not marked as sent yet."""
    return conn.execute(
        select(func.count())
        .select_from(appointment.join(patient, patient.c.id == appointment.c.patient_id))
        .where(
            appointment.c.practice_id == practice_id,
            *reminder_conditions(day),
            patient.c.reminder_consent.is_(True),
            appointment.c.reminder_sent_at.is_(None),
        )
    ).scalar_one()


@router.get("")
def reminders(user: StaffUser, ctx: Ctx, conn: Conn, day: date | None = None) -> list[ReminderOut]:
    day = day or today_tunis(ctx.clock) + timedelta(days=1)
    p = conn.execute(
        select(
            practice.c.name, practice.c.name_ar, practice.c.phone,
            practice.c.reminder_template_fr, practice.c.reminder_template_ar,
        ).where(practice.c.id == user.pid)
    ).one()
    items = load_appointments(conn, user.pid, *reminder_conditions(day))
    if not items:
        return []
    patients = {
        r.id: r
        for r in conn.execute(
            select(patient.c.id, patient.c.lang, patient.c.reminder_consent).where(
                patient.c.practice_id == user.pid, patient.c.id.in_({a.patient.id for a in items})
            )
        )
    }
    out = []
    for a in items:
        person = patients[a.patient.id]
        local = a.starts_at.astimezone(TUNIS)
        arabic = person.lang == "ar"
        values = {
            "patient": f"{a.patient.first_name} {a.patient.last_name}",
            "date": local.strftime("%d/%m/%Y"),
            "time": local.strftime("%H:%M"),
            "practice": (p.name_ar or p.name) if arabic else p.name,
            "phone": p.phone,
        }
        template = p.reminder_template_ar if arabic else p.reminder_template_fr
        out.append(
            ReminderOut(
                appointment=a,
                patient_lang=person.lang,
                reminder_consent=person.reminder_consent,
                phone_digits=phone_digits(a.patient.phone),
                message=render_message(template, values),
            )
        )
    return out
