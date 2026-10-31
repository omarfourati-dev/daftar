"""``/api/closures``: closing days and holidays of the practice (no appointments, no online bookings on them).

- ``GET ?from=&to=`` (every staff role) → ``[{id, startsOn, endsOn, label}]`` overlapping the range, by start;
- ``POST {startsOn, endsOn?, label?}`` (owner) → 201 the closure plus ``affectedAppointments`` – the number of
  appointments already booked in it (they stay; the practice decides whom to call);
- ``PATCH /{id}`` / ``DELETE /{id}`` (owner). At most one year per closure; ``endsOn`` defaults to ``startsOn``.

A change counts for the hygiene register from today on: the days before keep the plan they had
(:func:`daftar.hygiene_register.replan_today`).

"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import Field
from sqlalchemy import Connection, delete, func, insert, select, update

from .clock import today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, OwnerWriter, StaffUser
from .hygiene_register import replan_today, sync
from .problems import not_found, unprocessable
from .schemas import ApiModel
from .tables import FREEING_STATUSES, appointment, practice_closure

router = APIRouter(prefix="/api/closures", tags=["closures"])

MAX_SPAN = timedelta(days=366)
Label = Annotated[str, Field(max_length=120)]


class ClosureOut(ApiModel):
    id: int
    starts_on: date
    ends_on: date
    label: str


class CreatedClosure(ClosureOut):
    affected_appointments: int


class ClosureIn(ApiModel):
    starts_on: date
    ends_on: date | None = None
    label: Label = ""


class ClosurePatch(ApiModel):
    starts_on: date | None = None
    ends_on: date | None = None
    label: Label | None = None


def _check_range(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on or ends_on - starts_on > MAX_SPAN:
        raise unprocessable("La période doit finir après son début et durer au plus un an.", code="invalid_range")


def _get(conn: Connection, practice_id: int, closure_id: int) -> ClosureOut:
    row = conn.execute(
        select(practice_closure).where(practice_closure.c.id == closure_id, practice_closure.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    return ClosureOut.model_validate(row, from_attributes=True)


@router.get("")
def list_closures(
    user: StaffUser,
    conn: Conn,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> list[ClosureOut]:
    query = select(practice_closure).where(practice_closure.c.practice_id == user.pid)
    if from_ is not None:
        query = query.where(practice_closure.c.ends_on >= from_)
    if to is not None:
        query = query.where(practice_closure.c.starts_on <= to)
    rows = conn.execute(query.order_by(practice_closure.c.starts_on, practice_closure.c.id)).all()
    return [ClosureOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", status_code=201)
def create_closure(body: ClosureIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> CreatedClosure:
    ends_on = body.ends_on or body.starts_on
    _check_range(body.starts_on, ends_on)
    today = today_tunis(ctx.clock)
    sync(conn, user.pid, today)
    new_id = conn.execute(
        insert(practice_closure)
        .values(practice_id=user.pid, starts_on=body.starts_on, ends_on=ends_on, label=body.label)
        .returning(practice_closure.c.id)
    ).scalar_one()
    replan_today(conn, user.pid, today)
    start, _ = tunis_day_bounds(body.starts_on)
    _, end = tunis_day_bounds(ends_on)
    affected = conn.execute(
        select(func.count()).where(
            appointment.c.practice_id == user.pid,
            appointment.c.starts_at >= start,
            appointment.c.starts_at < end,
            appointment.c.status.notin_(FREEING_STATUSES),
        )
    ).scalar_one()
    return CreatedClosure(**_get(conn, user.pid, new_id).model_dump(), affected_appointments=affected)


@router.patch("/{closure_id}")
def patch_closure(closure_id: int, body: ClosurePatch, user: OwnerWriter, ctx: Ctx, conn: Conn) -> ClosureOut:
    current = _get(conn, user.pid, closure_id)
    values = {k: v for k, v in body.model_dump(exclude_unset=True, by_alias=False).items() if v is not None}
    _check_range(values.get("starts_on", current.starts_on), values.get("ends_on", current.ends_on))
    if values:
        today = today_tunis(ctx.clock)
        sync(conn, user.pid, today)
        conn.execute(update(practice_closure).where(practice_closure.c.id == closure_id).values(**values))
        replan_today(conn, user.pid, today)
    return _get(conn, user.pid, closure_id)


@router.delete("/{closure_id}", status_code=204)
def delete_closure(closure_id: int, user: OwnerWriter, ctx: Ctx, conn: Conn) -> Response:
    _get(conn, user.pid, closure_id)
    today = today_tunis(ctx.clock)
    sync(conn, user.pid, today)
    conn.execute(delete(practice_closure).where(practice_closure.c.id == closure_id))
    replan_today(conn, user.pid, today)
    return Response(status_code=204)
