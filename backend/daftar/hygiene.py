"""``/api/hygiene``: equipment, recurring hygiene and maintenance tasks, "Hygiène du jour", proofs and the register
(spec stock-hygiène 3, 5.1, 5.2, 8). Rhythm rules: :mod:`daftar.hygiene_rules`; the register's rows:
:mod:`daftar.hygiene_register` (every due date written down – a later change of the plan never rewrites the past).

Roles (section 3): every staff role reads and ticks; assistant and owner set up equipment and tasks; the owner
corrects proofs. Changes of equipment and tasks are in the change log (who, when, old → new – :mod:`daftar.audit`).

- ``GET /equipment`` (with ``labelCode`` – ``A1`` on the labels of an autoclave – and how many tasks and sterilisation
  cycles use it) · ``POST`` · ``PATCH /{id}`` · ``DELETE /{id}`` (only without tasks and cycles, else 409
  ``equipment_in_use``).
- ``GET /tasks`` → ``[Task]`` with ``nextDueOn`` (the open occurrence, else the next one) · ``POST`` · ``PATCH /{id}``
  (a new frequency clears the weekday / interval it does not use; a new rhythm, first date or a deactivation counts
  from today) · ``DELETE /{id}`` (only while nothing of it is in the register but today's open row, else 409
  ``task_in_use`` – deactivate it instead). 422 ``invalid_rhythm`` / ``invalid_equipment``.
- ``POST /starter`` → ``{equipment, tasks}``: the start plan of the specialty in the user's language, nothing twice;
  daily and weekly tasks start today (a weekly one on an opening day), monthly ones in a week, yearly ones in a month.
- ``GET /today`` → ``{day, open, items:[{taskId, title, equipmentName, frequency, instructions, dueOn, state:
  overdue|due|done, done}]}``: the open rows – overdue ones first, then today's – and what was ticked today. ``open``
  is also the navigation badge (``/api/badges`` ``hygiene``) and part of the dashboard.
- ``POST /tasks/{id}/done {dueOn?, result: ok|not_ok, note?}`` → 201 item: only the open row (422 ``not_due``), once
  (409 ``already_done``), not for a deactivated task (422 ``task_inactive``).
- ``PATCH /done/{id} {result?, note?, reason}`` (owner) → the corrected proof, logged old → new with the reason.
- ``DELETE /done/{id} {reason?}`` → 204: its author within 15 minutes (a wrong tap, no reason needed), the owner
  always with a reason (422 ``reason_required``); logged. The row is open again while it is the current occurrence,
  else "non fait".
- ``GET /history?from=&to=&equipmentId=`` (at most 366 days, 422 ``invalid_range``) → the register: every written due
  date with its proof – ``done`` (``late`` when ticked after its day), ``missed``, ``overdue`` (still to do) or – today
  – ``due``; newest first, printable for an inspection.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Query, Response
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import Connection, delete, exists, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import audit
from .clock import TUNIS, today_tunis, tunis_day_bounds
from .db import constraint_name
from .deps import Conn, Ctx, OwnerWriter, Principal, StaffUser, StaffWriter
from .hygiene_register import (
    close_task,
    open_count,
    open_days,
    reopen_task,
    replan_today,
    rhythm_of,
    sync,
)
from .hygiene_rules import MAX_SHIFT_DAYS, EquipmentKind, Frequency, Rhythm, next_due, open_weekday, starter_plan
from .problems import ApiError, conflict, forbidden, not_found, unprocessable
from .schemas import ApiModel, Name, TunisDateTime
from .tables import equipment, hygiene_task, hygiene_task_done, hygiene_task_due, practice, sterilization_cycle

router = APIRouter(prefix="/api/hygiene", tags=["hygiene"])

MANAGERS = ("owner", "assistant")
UNDO_WINDOW = timedelta(minutes=15)
MAX_HISTORY_DAYS = 366
Note = Annotated[str, Field(max_length=500)]
Reason = Annotated[str, Field(max_length=300)]
RequiredReason = Annotated[str, Field(min_length=1, max_length=300)]
Instructions = Annotated[str, Field(max_length=1000)]
SerialNumber = Annotated[str, Field(max_length=60)]
Weekday = Annotated[int, Field(ge=1, le=7, strict=True)]
Interval = Annotated[int, Field(strict=True)]
Result = Literal["ok", "not_ok"]
State = Literal["overdue", "due", "done"]


def _manager(user: StaffWriter) -> Principal:
    if user.role not in MANAGERS:
        raise forbidden()
    return user


#: Sets up equipment and tasks (assistant, owner; subscription not suspended).
HygieneManager = Annotated[Principal, Depends(_manager)]


def _rhythm(frequency: str, starts_on: date, weekday: int | None, interval_days: int | None) -> Rhythm:
    return Rhythm(frequency, starts_on=starts_on, weekday=weekday, interval_days=interval_days)  # type: ignore[arg-type]


# --- equipment --------------------------------------------------------------------------------------------------


class EquipmentOut(ApiModel):
    id: int
    name: str
    kind: EquipmentKind
    serial_number: str
    note: str
    active: bool
    label_code: str | None
    tasks: int
    cycles: int


class EquipmentIn(ApiModel):
    name: Name
    kind: EquipmentKind = "autre"
    serial_number: SerialNumber = ""
    note: Note = ""
    active: StrictBool = True


class EquipmentPatch(ApiModel):
    name: Name | None = None
    kind: EquipmentKind | None = None
    serial_number: SerialNumber | None = None
    note: Note | None = None
    active: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> EquipmentPatch:
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


#: Column → key in the change log.
EQUIPMENT_LOG = {"name": "name", "kind": "kind", "serial_number": "serialNumber", "note": "note", "active": "active"}


def _equipment(conn: Connection, practice_id: int, equipment_id: int | None = None) -> list[EquipmentOut]:
    count = select(func.count()).where(hygiene_task.c.equipment_id == equipment.c.id).scalar_subquery()
    cycles = select(func.count()).where(sterilization_cycle.c.equipment_id == equipment.c.id).scalar_subquery()
    conditions = [equipment.c.practice_id == practice_id]
    if equipment_id is not None:
        conditions.append(equipment.c.id == equipment_id)
    rows = conn.execute(
        select(equipment, count.label("tasks"), cycles.label("cycles"))
        .where(*conditions).order_by(func.lower(equipment.c.name), equipment.c.id)
    ).all()
    return [EquipmentOut.model_validate(r, from_attributes=True) for r in rows]


def _one_equipment(conn: Connection, practice_id: int, equipment_id: int) -> EquipmentOut:
    found = _equipment(conn, practice_id, equipment_id)
    if not found:
        raise not_found()
    return found[0]


def _equipment_exists() -> ApiError:
    return conflict("Un équipement porte déjà ce nom.", code="equipment_exists")


def _write(conn: Connection, statement: Any, constraint: str, error: Callable[[], ApiError]) -> Any:
    try:
        with conn.begin_nested():
            return conn.execute(statement)
    except IntegrityError as exc:
        if constraint_name(exc) == constraint:
            raise error() from exc
        raise


@router.get("/equipment")
def list_equipment(user: StaffUser, conn: Conn) -> list[EquipmentOut]:
    return _equipment(conn, user.pid)


@router.post("/equipment", status_code=201)
def create_equipment(body: EquipmentIn, user: HygieneManager, ctx: Ctx, conn: Conn) -> EquipmentOut:
    new_id = _write(
        conn,
        insert(equipment).values(practice_id=user.pid, created_at=ctx.clock.now(), **body.model_dump(by_alias=False))
        .returning(equipment.c.id),
        "equipment_name_key",
        _equipment_exists,
    ).scalar_one()
    return _one_equipment(conn, user.pid, new_id)


@router.patch("/equipment/{equipment_id}")
def patch_equipment(equipment_id: int, body: EquipmentPatch, user: HygieneManager, ctx: Ctx, conn: Conn) -> EquipmentOut:
    current = _one_equipment(conn, user.pid, equipment_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    before, after = audit.diff(current.model_dump(by_alias=False), values, EQUIPMENT_LOG)
    if after:
        _write(conn, update(equipment).where(equipment.c.id == equipment_id).values(**values), "equipment_name_key",
               _equipment_exists)
        if "name" in after:  # what is still to do reads the new name; the past keeps the old one
            conn.execute(update(hygiene_task_due)
                         .where(hygiene_task_due.c.equipment_id == equipment_id, hygiene_task_due.c.status == "open")
                         .values(equipment_name=values["name"]))
        audit.record(conn, user, entity="equipment", entity_id=equipment_id, action="update", now=ctx.clock.now(),
                     before={"equipment": current.name, **before}, after=after)
    return _one_equipment(conn, user.pid, equipment_id)


@router.delete("/equipment/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int, user: HygieneManager, ctx: Ctx, conn: Conn) -> Response:
    current = _one_equipment(conn, user.pid, equipment_id)
    if current.tasks or current.cycles:
        raise conflict("Des tâches ou des cycles utilisent cet équipement : désactivez-le plutôt.", code="equipment_in_use")
    audit.record(conn, user, entity="equipment", entity_id=equipment_id, action="delete", now=ctx.clock.now(),
                 before={"name": current.name, "kind": current.kind, "serialNumber": current.serial_number})
    conn.execute(delete(equipment).where(equipment.c.id == equipment_id))
    return Response(status_code=204)


# --- tasks ------------------------------------------------------------------------------------------------------


class TaskOut(ApiModel):
    id: int
    title: str
    equipment_id: int | None
    equipment_name: str | None
    frequency: Frequency
    weekday: int | None
    interval_days: int | None
    starts_on: date
    instructions: str
    active: bool
    next_due_on: date | None


class TaskIn(ApiModel):
    title: Name
    equipment_id: int | None = None
    frequency: Frequency
    weekday: Weekday | None = None
    interval_days: Interval | None = None
    starts_on: date | None = None
    instructions: Instructions = ""
    active: StrictBool = True

    @model_validator(mode="after")
    def _rhythm_is_complete(self) -> TaskIn:
        _rhythm(self.frequency, self.starts_on or date.min, self.weekday, self.interval_days)
        return self


class TaskPatch(ApiModel):
    title: Name | None = None
    equipment_id: int | None = None
    frequency: Frequency | None = None
    weekday: Weekday | None = None
    interval_days: Interval | None = None
    starts_on: date | None = None
    instructions: Instructions | None = None
    active: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null(self) -> TaskPatch:
        for name in self.model_fields_set - {"equipment_id", "weekday", "interval_days"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


RHYTHM_FIELDS = ("frequency", "weekday", "interval_days", "starts_on")
#: Field → key in the change log (the equipment by its name, so the log stays readable).
TASK_LOG = {"title": "title", "equipment": "equipment", "frequency": "frequency", "weekday": "weekday",
            "interval_days": "intervalDays", "starts_on": "startsOn", "instructions": "instructions", "active": "active"}
#: How far ahead the next due date is looked for (a yearly task, a closed day at the end).
LOOK_AHEAD_DAYS = 500


def _task_rows(conn: Connection, practice_id: int, *conditions: Any) -> list[Any]:
    return conn.execute(
        select(hygiene_task, equipment.c.name.label("equipment_name"))
        .select_from(hygiene_task.outerjoin(equipment, equipment.c.id == hygiene_task.c.equipment_id))
        .where(hygiene_task.c.practice_id == practice_id, *conditions)
        .order_by(func.lower(hygiene_task.c.title), hygiene_task.c.id)
    ).all()


def load_tasks(conn: Connection, practice_id: int, today: date, *conditions: Any) -> list[TaskOut]:
    """The tasks with their open occurrence, else the next one (call :func:`sync` before)."""
    rows = _task_rows(conn, practice_id, *conditions)
    if not rows:
        return []
    current = dict(conn.execute(
        select(hygiene_task_due.c.task_id, func.min(hygiene_task_due.c.due_on))
        .where(hygiene_task_due.c.task_id.in_([r.id for r in rows]), hygiene_task_due.c.status == "open")
        .group_by(hygiene_task_due.c.task_id)
    ).all())
    is_open = open_days(conn, practice_id, today - timedelta(days=MAX_SHIFT_DAYS), today + timedelta(days=LOOK_AHEAD_DAYS))
    return [
        TaskOut(
            id=r.id, title=r.title, equipment_id=r.equipment_id, equipment_name=r.equipment_name, frequency=r.frequency,
            weekday=r.weekday, interval_days=r.interval_days, starts_on=r.starts_on, instructions=r.instructions,
            active=r.active,
            next_due_on=(current.get(r.id) or next_due(rhythm_of(r), today, is_open)) if r.active else None,
        )
        for r in rows
    ]


def _task(conn: Connection, practice_id: int, task_id: int) -> Any:
    rows = _task_rows(conn, practice_id, hygiene_task.c.id == task_id)
    if not rows:
        raise not_found()
    return rows[0]


def _check_equipment(conn: Connection, practice_id: int, equipment_id: int | None) -> str | None:
    """The name of the practice's equipment (None without one); 422 ``invalid_equipment`` for another one."""
    if equipment_id is None:
        return None
    found = conn.execute(
        select(equipment.c.name).where(equipment.c.id == equipment_id, equipment.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise unprocessable("Cet équipement n'existe pas dans le cabinet.", code="invalid_equipment")
    return str(found.name)


def _one_task(conn: Connection, practice_id: int, task_id: int, today: date) -> TaskOut:
    return load_tasks(conn, practice_id, today, hygiene_task.c.id == task_id)[0]


@router.get("/tasks")
def list_tasks(user: StaffUser, ctx: Ctx, conn: Conn) -> list[TaskOut]:
    today = today_tunis(ctx.clock)
    sync(conn, user.pid, today)
    return load_tasks(conn, user.pid, today)


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, user: HygieneManager, ctx: Ctx, conn: Conn) -> TaskOut:
    _check_equipment(conn, user.pid, body.equipment_id)
    today = today_tunis(ctx.clock)
    values = body.model_dump(by_alias=False)
    values["starts_on"] = values["starts_on"] or today
    new_id = conn.execute(
        insert(hygiene_task).values(practice_id=user.pid, created_at=ctx.clock.now(), **values).returning(hygiene_task.c.id)
    ).scalar_one()
    sync(conn, user.pid, today, [new_id])
    return _one_task(conn, user.pid, new_id, today)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, user: HygieneManager, ctx: Ctx, conn: Conn) -> TaskOut:
    row = _task(conn, user.pid, task_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    equipment_name = _check_equipment(conn, user.pid, values["equipment_id"]) if "equipment_id" in values else row.equipment_name
    merged = {k: getattr(row, k) for k in RHYTHM_FIELDS} | {k: v for k, v in values.items() if k in RHYTHM_FIELDS}
    if merged["frequency"] != "weekly" and "weekday" not in values:
        merged["weekday"] = None  # a new rhythm does not keep the details of the old one
    if merged["frequency"] != "every_n_days" and "interval_days" not in values:
        merged["interval_days"] = None
    try:
        _rhythm(merged["frequency"], merged["starts_on"], merged["weekday"], merged["interval_days"])
    except ValueError as exc:
        code, _, detail = str(exc).partition(": ")
        raise unprocessable(detail, code=code) from exc
    values.update(merged)
    changed = {k: v for k, v in values.items() if getattr(row, k) != v}
    today = today_tunis(ctx.clock)
    if not changed:
        return _one_task(conn, user.pid, task_id, today)
    sync(conn, user.pid, today, [task_id])  # the days before today keep the plan they had
    conn.execute(update(hygiene_task).where(hygiene_task.c.id == task_id).values(**changed))
    if "title" in changed or "equipment_id" in changed:  # what is still to do reads the new names
        conn.execute(update(hygiene_task_due)
                     .where(hygiene_task_due.c.task_id == task_id, hygiene_task_due.c.status == "open")
                     .values(title=values.get("title", row.title), equipment_id=values.get("equipment_id", row.equipment_id),
                             equipment_name=equipment_name))
    if "active" in changed:
        (reopen_task if changed["active"] else close_task)(conn, user.pid, task_id, today)
    elif row.active and changed.keys() & set(RHYTHM_FIELDS):
        replan_today(conn, user.pid, today, [task_id])
    old = {k: getattr(row, k) for k in TASK_LOG if k != "equipment"} | {"equipment": row.equipment_name}
    new = old | {k: v for k, v in changed.items() if k in TASK_LOG} | {"equipment": equipment_name}
    before, after = audit.diff(old, new, TASK_LOG)
    if after:
        audit.record(conn, user, entity="hygiene_task", entity_id=task_id, action="update", now=ctx.clock.now(),
                     before={"task": row.title, **before}, after=after)
    return _one_task(conn, user.pid, task_id, today)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user: HygieneManager, ctx: Ctx, conn: Conn) -> Response:
    row = _task(conn, user.pid, task_id)
    today = today_tunis(ctx.clock)
    sync(conn, user.pid, today, [task_id])
    in_register = or_(
        exists().where(hygiene_task_done.c.task_id == task_id),
        exists().where(hygiene_task_due.c.task_id == task_id,
                       (hygiene_task_due.c.due_on < today) | (hygiene_task_due.c.status != "open")),
    )
    if conn.execute(select(in_register)).scalar_one():
        raise conflict("Cette tâche est déjà dans le registre : désactivez-la plutôt.", code="task_in_use")
    audit.record(conn, user, entity="hygiene_task", entity_id=task_id, action="delete", now=ctx.clock.now(),
                 before={"title": row.title, "equipment": row.equipment_name, "frequency": row.frequency,
                         "weekday": row.weekday, "intervalDays": row.interval_days, "startsOn": row.starts_on})
    conn.execute(delete(hygiene_task_due).where(hygiene_task_due.c.task_id == task_id))
    conn.execute(delete(hygiene_task).where(hygiene_task.c.id == task_id))
    return Response(status_code=204)


class StarterOut(ApiModel):
    equipment: int
    tasks: int


#: First due date of a start-plan task, counted from today (time to plan the rare ones).
STARTER_DELAY = {"daily": 0, "weekly": 0, "every_n_days": 0, "monthly": 7, "yearly": 30}


@router.post("/starter")
def create_starter_plan(user: HygieneManager, ctx: Ctx, conn: Conn) -> StarterOut:
    place = conn.execute(select(practice.c.specialty, practice.c.weekly_hours).where(practice.c.id == user.pid)).one()
    plan = starter_plan(place.specialty)
    open_weekdays = {d for d in range(1, 8) if place.weekly_hours.get(str(d))}
    arabic = user.lang == "ar"
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    gear = {r.name.lower(): r.id for r in conn.execute(select(equipment.c.id, equipment.c.name).where(equipment.c.practice_id == user.pid))}
    titles = {t.lower() for t in conn.execute(select(hygiene_task.c.title).where(hygiene_task.c.practice_id == user.pid)).scalars()}
    keys: dict[str, int] = {}
    new_equipment = 0
    for e in plan.equipment:
        name = e.name_ar if arabic else e.name_fr
        if name.lower() not in gear:
            gear[name.lower()] = conn.execute(
                insert(equipment).values(practice_id=user.pid, name=name, kind=e.kind, created_at=now).returning(equipment.c.id)
            ).scalar_one()
            new_equipment += 1
        keys[e.key] = gear[name.lower()]
    rows = []
    for t in plan.tasks:
        title = t.title_ar if arabic else t.title_fr
        if title.lower() in titles:
            continue
        titles.add(title.lower())
        rows.append({
            "practice_id": user.pid, "title": title, "equipment_id": keys.get(t.equipment) if t.equipment else None,
            "frequency": t.frequency, "weekday": open_weekday(t.weekday, open_weekdays) if t.weekday else None,
            "interval_days": t.interval_days, "starts_on": today + timedelta(days=STARTER_DELAY[t.frequency]),
            "instructions": t.instructions_ar if arabic else t.instructions_fr, "created_at": now,
        })
    if rows:
        conn.execute(insert(hygiene_task), rows)
        sync(conn, user.pid, today)
    return StarterOut(equipment=new_equipment, tasks=len(rows))


# --- Hygiène du jour --------------------------------------------------------------------------------------------


class DoneOut(ApiModel):
    id: int
    done_by: str
    done_at: TunisDateTime
    result: Result
    note: str
    undoable: bool


class TodayItem(ApiModel):
    task_id: int
    title: str
    equipment_name: str | None
    frequency: Frequency
    instructions: str
    due_on: date
    state: State
    done: DoneOut | None


class TodayOut(ApiModel):
    day: date
    open: int
    items: list[TodayItem]


class HistoryDone(ApiModel):
    id: int
    done_by: str
    done_at: TunisDateTime
    result: Result
    note: str


class HistoryRow(ApiModel):
    due_on: date
    task_id: int
    title: str
    equipment_name: str | None
    status: Literal["done", "missed", "overdue", "due"]
    late: bool
    done: HistoryDone | None


class HistoryOut(ApiModel):
    from_: date = Field(alias="from")
    to: date
    rows: list[HistoryRow]


def _history_row(r: Any, today: date) -> HistoryRow:
    status = ("done" if r.done_id is not None else "missed" if r.status == "missed"
              else "due" if r.due_on == today else "overdue")
    return HistoryRow(
        due_on=r.due_on, task_id=r.task_id, title=r.title, equipment_name=r.equipment_name, status=status,
        late=r.done_id is not None and r.done_at.astimezone(TUNIS).date() > r.due_on,
        done=HistoryDone(id=r.done_id, done_by=r.done_by_name, done_at=r.done_at, result=r.result, note=r.note)
        if r.done_id is not None else None,
    )


def _quick_undo(user: Principal, row: Any, now: datetime) -> bool:
    """The author takes back a wrong tap within 15 minutes."""
    return row.done_by == user.user_id and now - row.done_at <= UNDO_WINDOW


def _undoable(user: Principal, row: Any, now: datetime) -> bool:
    return user.is_owner or _quick_undo(user, row, now)


def _done_out(user: Principal, row: Any, now: datetime) -> DoneOut:
    return DoneOut(id=row.done_id, done_by=row.done_by_name, done_at=row.done_at, result=row.result, note=row.note,
                   undoable=_undoable(user, row, now))


def _register_rows() -> Any:
    """Rows of the register with their task and proof (labels without clashes)."""
    return (
        select(
            hygiene_task_due.c.task_id, hygiene_task_due.c.due_on, hygiene_task_due.c.title,
            hygiene_task_due.c.equipment_name, hygiene_task_due.c.status, hygiene_task.c.frequency,
            hygiene_task.c.instructions, hygiene_task.c.active, hygiene_task_done.c.id.label("done_id"),
            hygiene_task_done.c.done_by, hygiene_task_done.c.done_by_name, hygiene_task_done.c.done_at,
            hygiene_task_done.c.result, hygiene_task_done.c.note,
        )
        .select_from(
            hygiene_task_due.join(hygiene_task, hygiene_task.c.id == hygiene_task_due.c.task_id)
            .outerjoin(hygiene_task_done, (hygiene_task_done.c.task_id == hygiene_task_due.c.task_id)
                       & (hygiene_task_done.c.due_on == hygiene_task_due.c.due_on))
        )
    )


def _item(user: Principal, row: Any, today: date, now: datetime) -> TodayItem:
    state: State = "done" if row.done_id is not None else "due" if row.due_on == today else "overdue"
    return TodayItem(task_id=row.task_id, title=row.title, equipment_name=row.equipment_name, frequency=row.frequency,
                     instructions=row.instructions, due_on=row.due_on, state=state,
                     done=_done_out(user, row, now) if row.done_id is not None else None)


def hygiene_today(conn: Connection, user: Principal, today: date, now: datetime) -> TodayOut:
    sync(conn, user.pid, today)
    day_start, _ = tunis_day_bounds(today)
    rows = conn.execute(
        _register_rows().where(
            hygiene_task_due.c.practice_id == user.pid, hygiene_task.c.active.is_(True),
            (hygiene_task_due.c.status == "open")
            | ((hygiene_task_due.c.status == "done")
               & ((hygiene_task_due.c.due_on == today) | (hygiene_task_done.c.done_at >= day_start))),
        )
    ).all()
    items = [_item(user, r, today, now) for r in rows]
    order = {"overdue": 0, "due": 1, "done": 2}
    items.sort(key=lambda i: (order[i.state], i.due_on, i.title.lower(), i.task_id))
    return TodayOut(day=today, open=sum(1 for i in items if i.state != "done"), items=items)


@router.get("/today")
def today_list(user: StaffUser, ctx: Ctx, conn: Conn) -> TodayOut:
    return hygiene_today(conn, user, today_tunis(ctx.clock), ctx.clock.now())


class DoneIn(ApiModel):
    due_on: date | None = None
    result: Result = "ok"
    note: Note = ""


def _already_done() -> ApiError:
    return conflict("Déjà fait.", code="already_done")


@router.post("/tasks/{task_id}/done", status_code=201)
def tick_task(task_id: int, body: DoneIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> TodayItem:
    row = _task(conn, user.pid, task_id)
    if not row.active:
        raise unprocessable("Cette tâche est désactivée.", code="task_inactive")
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    sync(conn, user.pid, today, [task_id])
    rows = conn.execute(
        select(hygiene_task_due).where(hygiene_task_due.c.task_id == task_id).order_by(hygiene_task_due.c.due_on.desc())
    ).all()
    current = next((r for r in rows if r.status == "open"), None)
    if current is None or (body.due_on is not None and body.due_on != current.due_on):
        wanted = body.due_on or (rows[0].due_on if rows else None)
        if any(r.due_on == wanted and r.status == "done" for r in rows):
            raise _already_done()
        raise unprocessable("Cette échéance n'est pas à faire maintenant.", code="not_due")
    _write(
        conn,
        insert(hygiene_task_done)
        .values(practice_id=user.pid, task_id=task_id, due_on=current.due_on, done_by=user.user_id,
                done_by_name=user.name[:120], done_at=now, result=body.result, note=body.note),
        "hygiene_task_done_once",
        _already_done,
    )
    conn.execute(update(hygiene_task_due).where(hygiene_task_due.c.id == current.id).values(status="done"))
    (done,) = conn.execute(
        _register_rows().where(hygiene_task_due.c.id == current.id)
    ).all()
    return _item(user, done, today, now)


class UndoIn(ApiModel):
    reason: Reason = ""


class CorrectionIn(ApiModel):
    result: Result | None = None
    note: Note | None = None
    reason: RequiredReason


def _proof(conn: Connection, practice_id: int, done_id: int) -> Any:
    row = conn.execute(
        _register_rows().where(hygiene_task_done.c.id == done_id, hygiene_task_done.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    return row


def _proof_log(row: Any) -> dict[str, Any]:
    return {"task": row.title, "dueOn": row.due_on, "doneBy": row.done_by_name, "doneAt": row.done_at,
            "result": row.result, "note": row.note}


@router.patch("/done/{done_id}")
def correct_proof(done_id: int, body: CorrectionIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> HistoryRow:
    row = _proof(conn, user.pid, done_id)
    values = {k: v for k, v in body.model_dump(exclude_unset=True, by_alias=False).items()
              if k in ("result", "note") and v is not None}
    _, after = audit.diff({"result": row.result, "note": row.note}, values, {"result": "result", "note": "note"})
    if after:
        conn.execute(update(hygiene_task_done).where(hygiene_task_done.c.id == done_id).values(**values))
        audit.record(conn, user, entity="hygiene_task_done", entity_id=done_id, action="update", now=ctx.clock.now(),
                     before=_proof_log(row), after=after, reason=body.reason.strip())
    return _history_row(_proof(conn, user.pid, done_id), today_tunis(ctx.clock))


@router.delete("/done/{done_id}", status_code=204)
def undo(done_id: int, user: StaffWriter, ctx: Ctx, conn: Conn,
         body: Annotated[UndoIn | None, Body()] = None) -> Response:
    row = _proof(conn, user.pid, done_id)
    now = ctx.clock.now()
    quick = _quick_undo(user, row, now)
    if not (quick or user.is_owner):
        if row.done_by == user.user_id:
            raise forbidden("Seule la personne titulaire peut annuler après 15 minutes.", code="undo_too_late")
        raise forbidden()
    reason = body.reason.strip() if body else ""
    if not quick and not reason:
        raise unprocessable("Indiquez le motif de l'annulation.", code="reason_required")
    audit.record(conn, user, entity="hygiene_task_done", entity_id=done_id, action="delete", now=now,
                 before=_proof_log(row), reason=reason)
    conn.execute(delete(hygiene_task_done).where(hygiene_task_done.c.id == done_id))
    replaced = conn.execute(select(exists().where(hygiene_task_due.c.task_id == row.task_id,
                                                  hygiene_task_due.c.due_on > row.due_on))).scalar_one()
    conn.execute(
        update(hygiene_task_due)
        .where(hygiene_task_due.c.task_id == row.task_id, hygiene_task_due.c.due_on == row.due_on)
        .values(status="open" if row.active and not replaced else "missed")
    )
    return Response(status_code=204)


# --- history (the register) -------------------------------------------------------------------------------------


@router.get("/history")
def history(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    first: Annotated[date | None, Query(alias="from")] = None,
    last: Annotated[date | None, Query(alias="to")] = None,
    equipment_id: Annotated[int | None, Query(alias="equipmentId")] = None,
) -> HistoryOut:
    today = today_tunis(ctx.clock)
    last = last or today
    first = first or last - timedelta(days=29)
    if last < first or (last - first).days >= MAX_HISTORY_DAYS:
        raise unprocessable("Choisissez une période d'un an au plus.", code="invalid_range")
    sync(conn, user.pid, today)
    conditions = [hygiene_task_due.c.practice_id == user.pid, hygiene_task_due.c.due_on >= first,
                  hygiene_task_due.c.due_on <= last]
    if equipment_id is not None:
        conditions.append(hygiene_task_due.c.equipment_id == equipment_id)
    rows = conn.execute(
        _register_rows().where(*conditions)
        .order_by(hygiene_task_due.c.due_on.desc(), func.lower(hygiene_task_due.c.title), hygiene_task_due.c.task_id)
    ).all()
    return HistoryOut(from_=first, to=last, rows=[_history_row(r, today) for r in rows])


def open_tasks(conn: Connection, user: Principal, today: date) -> int:
    """Overdue and due tasks – the navigation badge."""
    return open_count(conn, user.pid, today)
