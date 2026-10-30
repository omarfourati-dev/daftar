"""``GET /api/availability?date=&durationMin=&practitionerId=`` (section 11.1, every staff role).

→ ``{date, slots: [{time: "09:15", practitionerIds: [...]}]}`` – starts on the practice's grid inside the opening
hours of that weekday, without closing days, booked times or the past; ``practitionerIds`` lists the active
practitioners free for the whole duration (empty for a practice without practitioners: its one calendar is free).
``durationMin`` defaults to the practice's default duration. The online booking uses the same rules.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import Connection, select

from .clock import TUNIS
from .deps import Conn, Ctx, StaffUser
from .problems import not_found
from .scheduling import free_starts, load_calendar
from .schemas import ApiModel
from .tables import practitioner

router = APIRouter(prefix="/api/availability", tags=["appointments"])


class Slot(ApiModel):
    time: str
    practitioner_ids: list[int]


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
