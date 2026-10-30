"""``GET /api/availability?date=&durationMin=&practitionerId=`` (section 11.1, every staff role).

→ ``{date, slots: [{time: "09:15", practitionerIds: [...]}]}`` – starts on the practice's grid inside the opening
hours of that weekday, without closing days, booked times or the past; ``practitionerIds`` lists the active
practitioners free for the whole duration (empty for a practice without practitioners: its one calendar is free).
``durationMin`` defaults to the practice's default duration. The online booking uses the same rules.

``GET /api/availability/next?serviceId=&practitionerId=&patientId=&durationMin=&limit=8`` (section 16.1, the phone
booking) → ``[{startsAt, practitionerId}]``: the next free starts from now on, over the days up to today + 14, each
with the first free practitioner (practice order; null without practitioners). Duration: ``durationMin``, else the
service's, else the practice default; with ``patientId`` the patient must be free too.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import Connection, select

from .appointments import check_patient, check_service
from .clock import TUNIS, today_tunis
from .deps import Conn, Ctx, StaffUser
from .problems import not_found
from .scheduling import closed_days, free_starts, load_calendar
from .schemas import ApiModel, TunisDateTime
from .tables import practitioner

router = APIRouter(prefix="/api/availability", tags=["appointments"])


class Slot(ApiModel):
    time: str
    practitioner_ids: list[int]


class NextSlot(ApiModel):
    starts_at: TunisDateTime
    practitioner_id: int | None


#: How far ``/next`` looks ahead (days after today).
NEXT_DAYS = 14


class AvailabilityOut(ApiModel):
    date: date
    slots: list[Slot]


def staff_resources(conn: Connection, practice_id: int, practitioner_id: int | None) -> list[int | None]:
    """The calendars to look at: the given practitioner (404 if foreign), else every active one, else "none"."""
    if practitioner_id is not None:
        found = conn.execute(
            select(practitioner.c.id).where(practitioner.c.id == practitioner_id, practitioner.c.practice_id == practice_id)
        ).first()
        if found is None:
            raise not_found()
        return [practitioner_id]
    active = conn.execute(
        select(practitioner.c.id)
        .where(practitioner.c.practice_id == practice_id, practitioner.c.active)
        .order_by(practitioner.c.sort, practitioner.c.id)
    ).scalars().all()
    return list(active) or [None]


@router.get("")
def availability(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    date_: Annotated[date, Query(alias="date")],
    duration_min: Annotated[int | None, Query(alias="durationMin"), Field(ge=5, le=480)] = None,
    practitioner_id: Annotated[int | None, Query(alias="practitionerId")] = None,
) -> AvailabilityOut:
    cal = load_calendar(conn, user.pid)
    resources = staff_resources(conn, user.pid, practitioner_id)
    found = free_starts(conn, cal, date_, duration_min or cal.default_duration_min, resources, not_before=ctx.clock.now())
    return AvailabilityOut(
        date=date_,
        slots=[Slot(time=t.astimezone(TUNIS).strftime("%H:%M"), practitioner_ids=[r for r in free if r is not None])
               for t, free in found],
    )


@router.get("/next")
def next_free(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    service_id: Annotated[int | None, Query(alias="serviceId")] = None,
    practitioner_id: Annotated[int | None, Query(alias="practitionerId")] = None,
    patient_id: Annotated[int | None, Query(alias="patientId")] = None,
    duration_min: Annotated[int | None, Query(alias="durationMin"), Field(ge=5, le=480)] = None,
    limit: Annotated[int, Query(), Field(ge=1, le=50)] = 8,
) -> list[NextSlot]:
    svc = check_service(conn, user.pid, service_id)
    if patient_id is not None:
        check_patient(conn, user.pid, patient_id)
    cal = load_calendar(conn, user.pid)
    resources = staff_resources(conn, user.pid, practitioner_id)
    duration = duration_min or (svc.duration_min if svc else cal.default_duration_min)
    today, now = today_tunis(ctx.clock), ctx.clock.now()
    closed = closed_days(conn, user.pid, today, today + timedelta(days=NEXT_DAYS))
    found: list[NextSlot] = []
    for offset in range(NEXT_DAYS + 1):
        for t, free in free_starts(conn, cal, today + timedelta(days=offset), duration, resources, not_before=now,
                                   patient_id=patient_id, closed=closed):
            found.append(NextSlot(starts_at=t, practitioner_id=free[0]))
            if len(found) == limit:
                return found
    return found
