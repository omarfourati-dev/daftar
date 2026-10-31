"""The hygiene register as a document (spec stock-hygiène 1, 5.2, 8 – review H1): every due date of a task is written
down as its own row (``hygiene_task_due``) and from then on only changes by a proof, never by a change of the plan.

- **Written up to today** (:func:`sync`): hourly by the job :func:`sync_all`, and on every read of the hygiene pages,
  the dashboard and the badge in case the job did not run. A task's rows start on the day it was created – a first
  date ("Première fois") in the past only sets the rhythm; nothing before Daftar knew the task becomes "non fait".
- **Status**: ``open`` while it is the task's current occurrence (to do today, or overdue), ``done`` with a proof,
  ``missed`` once a newer occurrence replaced it (or the task was deactivated) without a proof. ``missed`` is final.
- **Changes of the plan count from today** (:func:`replan_today`): a new rhythm or first date, a deactivation, new
  opening hours or a closure. The rows up to yesterday are written first with the old plan; today's row goes when it
  is still open and comes back if the new plan wants it. Title and equipment are copied into each row: renaming changes
  the open rows only.
- **Cheap badge** (:func:`open_count`): one indexed check whether something is to write, then a count of the open rows.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import aliased

from .clock import TUNIS, today_tunis
from .context import AppContext
from .hours import windows_for
from .hygiene_rules import MAX_SHIFT_DAYS, Rhythm, occurrences
from .scheduling import closed_days
from .tables import equipment, hygiene_task, hygiene_task_done, hygiene_task_due, practice

log = logging.getLogger("daftar")

OpenDay = Callable[[date], bool]


def open_days(conn: Connection, practice_id: int, first: date, last: date) -> OpenDay:
    """Opening days of the practice in ``[first, last]``: weekly hours, no closure."""
    weekly_hours = conn.execute(select(practice.c.weekly_hours).where(practice.c.id == practice_id)).scalar_one()
    closed = closed_days(conn, practice_id, first, last)
    return lambda day: bool(windows_for(weekly_hours, day)) and day not in closed


def rhythm_of(row: Any) -> Rhythm:
    return Rhythm(row.frequency, starts_on=row.starts_on, weekday=row.weekday, interval_days=row.interval_days)


def created_on(row: Any) -> date:
    return row.created_at.astimezone(TUNIS).date()


def _stale(practice_id: int, today: date, task_ids: Sequence[int] | None) -> list[Any]:
    conditions = [
        hygiene_task.c.practice_id == practice_id,
        hygiene_task.c.active.is_(True),
        (hygiene_task.c.materialized_until.is_(None)) | (hygiene_task.c.materialized_until < today),
    ]
    if task_ids is not None:
        conditions.append(hygiene_task.c.id.in_(task_ids))
    return conditions


def needs_sync(conn: Connection, practice_id: int, today: date) -> bool:
    return bool(conn.execute(select(exists().where(*_stale(practice_id, today, None)))).scalar_one())


def sync(conn: Connection, practice_id: int, today: date, task_ids: Sequence[int] | None = None) -> None:
    """Writes the rows of the active tasks up to ``today`` and settles their status."""
    tasks = conn.execute(
        select(hygiene_task, equipment.c.name.label("equipment_name"))
        .select_from(hygiene_task.outerjoin(equipment, equipment.c.id == hygiene_task.c.equipment_id))
        .where(*_stale(practice_id, today, task_ids))
        .order_by(hygiene_task.c.id)
    ).all()
    if not tasks:
        return
    starts = {
        t.id: max(t.materialized_until + timedelta(days=1), created_on(t)) if t.materialized_until else created_on(t)
        for t in tasks
    }
    first = min(starts.values())
    rows: list[dict[str, Any]] = []
    if first <= today:
        is_open = open_days(conn, practice_id, first - timedelta(days=MAX_SHIFT_DAYS), today)
        for t in tasks:
            rows += [
                {"practice_id": practice_id, "task_id": t.id, "due_on": day, "title": t.title,
                 "equipment_id": t.equipment_id, "equipment_name": t.equipment_name, "status": "open"}
                for day in occurrences(rhythm_of(t), starts[t.id], today, is_open)
            ]
    if rows:
        conn.execute(pg_insert(hygiene_task_due).values(rows).on_conflict_do_nothing(constraint="hygiene_task_due_once"))
    ids = [t.id for t in tasks]
    conn.execute(update(hygiene_task).where(hygiene_task.c.id.in_(ids)).values(materialized_until=today))
    settle(conn, ids)


def settle(conn: Connection, task_ids: Sequence[int]) -> None:
    """A proof makes its row done (demo data); an open row that a newer row replaced is a gap."""
    if not task_ids:
        return
    conn.execute(
        update(hygiene_task_due)
        .where(hygiene_task_due.c.task_id.in_(task_ids), hygiene_task_due.c.status == "open",
               exists().where(hygiene_task_done.c.task_id == hygiene_task_due.c.task_id,
                              hygiene_task_done.c.due_on == hygiene_task_due.c.due_on))
        .values(status="done")
    )
    later = aliased(hygiene_task_due)
    conn.execute(
        update(hygiene_task_due)
        .where(hygiene_task_due.c.task_id.in_(task_ids), hygiene_task_due.c.status == "open",
               exists().where(later.c.task_id == hygiene_task_due.c.task_id, later.c.due_on > hygiene_task_due.c.due_on))
        .values(status="missed")
    )


def replan_today(conn: Connection, practice_id: int, today: date, task_ids: Sequence[int] | None = None) -> None:
    """After a change of the plan: today's open rows go and today is planned again with what holds now (call
    :func:`sync` before the change, so the days before are written with the old plan)."""
    conditions = [hygiene_task_due.c.practice_id == practice_id, hygiene_task_due.c.due_on == today,
                  hygiene_task_due.c.status == "open"]
    tasks = [hygiene_task.c.practice_id == practice_id, hygiene_task.c.materialized_until >= today]
    if task_ids is not None:
        conditions.append(hygiene_task_due.c.task_id.in_(task_ids))
        tasks.append(hygiene_task.c.id.in_(task_ids))
    conn.execute(delete(hygiene_task_due).where(*conditions))
    conn.execute(update(hygiene_task).where(*tasks).values(materialized_until=today - timedelta(days=1)))
    sync(conn, practice_id, today, task_ids)


def close_task(conn: Connection, practice_id: int, task_id: int, today: date) -> None:
    """A deactivated task: today's open row goes (the change counts from today), earlier open ones are gaps."""
    conn.execute(delete(hygiene_task_due).where(hygiene_task_due.c.task_id == task_id, hygiene_task_due.c.due_on == today,
                                                hygiene_task_due.c.status == "open"))
    conn.execute(update(hygiene_task_due).where(hygiene_task_due.c.task_id == task_id, hygiene_task_due.c.status == "open")
                 .values(status="missed"))


def reopen_task(conn: Connection, practice_id: int, task_id: int, today: date) -> None:
    """A reactivated task: due again from today – the days it was off stay empty."""
    conn.execute(update(hygiene_task).where(hygiene_task.c.id == task_id)
                 .values(materialized_until=today - timedelta(days=1)))
    sync(conn, practice_id, today, [task_id])


def open_count(conn: Connection, practice_id: int, today: date) -> int:
    """Overdue and due tasks – the navigation badge (``/api/badges`` every minute: one check, one count)."""
    if needs_sync(conn, practice_id, today):
        sync(conn, practice_id, today)
    return int(conn.execute(
        select(func.count()).where(hygiene_task_due.c.practice_id == practice_id, hygiene_task_due.c.status == "open")
    ).scalar_one())


def sync_all(ctx: AppContext) -> None:
    """Job: today's rows for every practice, one transaction each."""
    today = today_tunis(ctx.clock)
    with ctx.engine.begin() as conn:
        practices = conn.execute(
            select(hygiene_task.c.practice_id).distinct()
            .where(hygiene_task.c.active.is_(True),
                   (hygiene_task.c.materialized_until.is_(None)) | (hygiene_task.c.materialized_until < today))
        ).scalars().all()
    for practice_id in practices:
        try:
            with ctx.engine.begin() as conn:
                sync(conn, practice_id, today)
        except Exception:  # one practice must not stop the others
            log.exception("hygiene register of practice %s failed", practice_id)
