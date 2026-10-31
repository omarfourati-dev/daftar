"""``/api/hygiene``: equipment, recurring hygiene and maintenance tasks, "Hygiène du jour", proofs and their history
(spec stock-hygiène 3, 5.1, 5.2, 8). Rhythm rules: :mod:`daftar.hygiene_rules`.

Roles (section 3): every staff role reads and ticks; assistant and owner set up equipment and tasks.

- ``GET /equipment`` · ``POST`` · ``PATCH /{id}`` · ``DELETE /{id}`` (only without tasks, else 409 ``equipment_in_use``).
- ``GET /tasks`` → ``[Task]`` with ``nextDueOn`` (the open occurrence, else the next one) · ``POST`` · ``PATCH /{id}``
  (a new frequency clears the weekday / interval it does not use) · ``DELETE /{id}`` (only without proofs, else 409
  ``task_in_use`` – deactivate it instead). 422 ``invalid_rhythm`` / ``invalid_equipment``.
- ``POST /starter`` → ``{equipment, tasks}``: the start plan of the specialty in the user's language, nothing twice;
  daily and weekly tasks start today, monthly ones in a week, yearly ones in a month (time to plan them).
- ``GET /today`` → ``{day, open, items:[{taskId, title, equipmentName, frequency, instructions, dueOn, state:
  overdue|due|done, done}]}``: per active task its current occurrence – overdue ones first, then today's, then what
  was ticked today. ``open`` is also the navigation badge (``/api/badges`` ``hygiene``) and part of the dashboard.
- ``POST /tasks/{id}/done {dueOn?, result: ok|not_ok, note?}`` → 201 item: only the current occurrence (422
  ``not_due``), once (409 ``already_done``), not for a deactivated task (422 ``task_inactive``).
- ``DELETE /done/{id}`` → 204: its author within 15 minutes (a wrong tap), the owner always; logged in the change log.
- ``GET /history?from=&to=&equipmentId=`` (at most 366 days, 422 ``invalid_range``) → every due date with its proof:
  ``done`` (``late`` when ticked after its day), ``missed`` or – today – ``due``; newest first, printable for an
  inspection.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import Connection, delete, exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import audit
from .clock import TUNIS, today_tunis
from .db import constraint_name
from .deps import Conn, Ctx, Principal, StaffUser, StaffWriter
from .hours import windows_for
from .hygiene_rules import EquipmentKind, Frequency, Rhythm, last_due, next_due, occurrences, starter_plan
from .problems import ApiError, conflict, forbidden, not_found, unprocessable
from .scheduling import closed_days
from .schemas import ApiModel, Name, TunisDateTime
from .tables import equipment, hygiene_task, hygiene_task_done, practice

router = APIRouter(prefix="/api/hygiene", tags=["hygiene"])

MANAGERS = ("owner", "assistant")
UNDO_WINDOW = timedelta(minutes=15)
MAX_HISTORY_DAYS = 366
Note = Annotated[str, Field(max_length=500)]
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


def open_days(conn: Connection, practice_id: int, first: date, last: date) -> Callable[[date], bool]:
    """Opening days of the practice in ``[first, last]``: weekly hours, no closure (for daily tasks)."""
    weekly_hours = conn.execute(select(practice.c.weekly_hours).where(practice.c.id == practice_id)).scalar_one()
    closed = closed_days(conn, practice_id, first, last)
    return lambda day: bool(windows_for(weekly_hours, day)) and day not in closed


# --- equipment --------------------------------------------------------------------------------------------------


class EquipmentOut(ApiModel):
    id: int
    name: str
    kind: EquipmentKind
    serial_number: str
    note: str
    active: bool
    tasks: int


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


def _equipment(conn: Connection, practice_id: int, equipment_id: int | None = None) -> list[EquipmentOut]:
    count = select(func.count()).where(hygiene_task.c.equipment_id == equipment.c.id).scalar_subquery()
    conditions = [equipment.c.practice_id == practice_id]
    if equipment_id is not None:
        conditions.append(equipment.c.id == equipment_id)
    rows = conn.execute(
        select(equipment, count.label("tasks")).where(*conditions).order_by(func.lower(equipment.c.name), equipment.c.id)
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
def patch_equipment(equipment_id: int, body: EquipmentPatch, user: HygieneManager, conn: Conn) -> EquipmentOut:
    _one_equipment(conn, user.pid, equipment_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    if values:
        _write(conn, update(equipment).where(equipment.c.id == equipment_id).values(**values), "equipment_name_key",
               _equipment_exists)
    return _one_equipment(conn, user.pid, equipment_id)


@router.delete("/equipment/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int, user: HygieneManager, conn: Conn) -> Response:
    if _one_equipment(conn, user.pid, equipment_id).tasks:
        raise conflict("Des tâches utilisent cet équipement : désactivez-le plutôt.", code="equipment_in_use")
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


def _task_rows(conn: Connection, practice_id: int, *conditions: Any) -> list[Any]:
    return conn.execute(
        select(hygiene_task, equipment.c.name.label("equipment_name"))
        .select_from(hygiene_task.outerjoin(equipment, equipment.c.id == hygiene_task.c.equipment_id))
        .where(hygiene_task.c.practice_id == practice_id, *conditions)
        .order_by(func.lower(hygiene_task.c.title), hygiene_task.c.id)
    ).all()


def _rhythm_of(row: Any) -> Rhythm:
    return _rhythm(row.frequency, row.starts_on, row.weekday, row.interval_days)


def _done_on(conn: Connection, practice_id: int, pairs: list[tuple[int, date]]) -> set[tuple[int, date]]:
    if not pairs:
        return set()
    days = {d for _, d in pairs}
    rows = conn.execute(
        select(hygiene_task_done.c.task_id, hygiene_task_done.c.due_on)
        .where(hygiene_task_done.c.practice_id == practice_id, hygiene_task_done.c.due_on.in_(days))
    ).all()
    return {(r.task_id, r.due_on) for r in rows}


def load_tasks(conn: Connection, practice_id: int, today: date, *conditions: Any) -> list[TaskOut]:
    rows = _task_rows(conn, practice_id, *conditions)
    if not rows:
        return []
    is_open = open_days(conn, practice_id, today - timedelta(days=400), today + timedelta(days=400))
    current = {r.id: last_due(_rhythm_of(r), today, is_open) for r in rows}
    done = _done_on(conn, practice_id, [(tid, d) for tid, d in current.items() if d is not None])
    result = []
    for r in rows:
        cur = current[r.id]
        nxt = cur if cur is not None and (r.id, cur) not in done else next_due(_rhythm_of(r), today if cur else today - timedelta(days=1), is_open)
        result.append(TaskOut(
            id=r.id, title=r.title, equipment_id=r.equipment_id, equipment_name=r.equipment_name, frequency=r.frequency,
            weekday=r.weekday, interval_days=r.interval_days, starts_on=r.starts_on, instructions=r.instructions,
            active=r.active, next_due_on=nxt if r.active else None,
        ))
    return result


def _task(conn: Connection, practice_id: int, task_id: int) -> Any:
    rows = _task_rows(conn, practice_id, hygiene_task.c.id == task_id)
    if not rows:
        raise not_found()
    return rows[0]


def _check_equipment(conn: Connection, practice_id: int, equipment_id: int | None) -> None:
    if equipment_id is None:
        return
    found = conn.execute(
        select(equipment.c.id).where(equipment.c.id == equipment_id, equipment.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise unprocessable("Cet équipement n'existe pas dans le cabinet.", code="invalid_equipment")


def _one_task(conn: Connection, practice_id: int, task_id: int, today: date) -> TaskOut:
    return load_tasks(conn, practice_id, today, hygiene_task.c.id == task_id)[0]


@router.get("/tasks")
def list_tasks(user: StaffUser, ctx: Ctx, conn: Conn) -> list[TaskOut]:
    return load_tasks(conn, user.pid, today_tunis(ctx.clock))


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, user: HygieneManager, ctx: Ctx, conn: Conn) -> TaskOut:
    _check_equipment(conn, user.pid, body.equipment_id)
    today = today_tunis(ctx.clock)
    values = body.model_dump(by_alias=False)
    values["starts_on"] = values["starts_on"] or today
    new_id = conn.execute(
        insert(hygiene_task).values(practice_id=user.pid, created_at=ctx.clock.now(), **values).returning(hygiene_task.c.id)
    ).scalar_one()
    return _one_task(conn, user.pid, new_id, today)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, user: HygieneManager, ctx: Ctx, conn: Conn) -> TaskOut:
    row = _task(conn, user.pid, task_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    if "equipment_id" in values:
        _check_equipment(conn, user.pid, values["equipment_id"])
    merged = {k: getattr(row, k) for k in ("frequency", "weekday", "interval_days", "starts_on")} | {
        k: v for k, v in values.items() if k in ("frequency", "weekday", "interval_days", "starts_on")
    }
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
    conn.execute(update(hygiene_task).where(hygiene_task.c.id == task_id).values(**values))
    return _one_task(conn, user.pid, task_id, today_tunis(ctx.clock))


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user: HygieneManager, conn: Conn) -> Response:
    _task(conn, user.pid, task_id)
    if conn.execute(select(exists().where(hygiene_task_done.c.task_id == task_id))).scalar_one():
        raise conflict("Cette tâche a des preuves enregistrées : désactivez-la plutôt.", code="task_in_use")
    conn.execute(delete(hygiene_task).where(hygiene_task.c.id == task_id))
    return Response(status_code=204)


class StarterOut(ApiModel):
    equipment: int
    tasks: int


#: First due date of a start-plan task, counted from today (time to plan the rare ones).
STARTER_DELAY = {"daily": 0, "weekly": 0, "every_n_days": 0, "monthly": 7, "yearly": 30}


@router.post("/starter")
def create_starter_plan(user: HygieneManager, ctx: Ctx, conn: Conn) -> StarterOut:
    specialty = conn.execute(select(practice.c.specialty).where(practice.c.id == user.pid)).scalar_one()
    plan = starter_plan(specialty)
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
            "frequency": t.frequency, "weekday": t.weekday, "interval_days": t.interval_days,
            "starts_on": today + timedelta(days=STARTER_DELAY[t.frequency]),
            "instructions": t.instructions_ar if arabic else t.instructions_fr, "created_at": now,
        })
    if rows:
        conn.execute(insert(hygiene_task), rows)
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


def _undoable(user: Principal, row: Any, now: datetime) -> bool:
    return user.is_owner or (row.done_by == user.user_id and now - row.done_at <= UNDO_WINDOW)


def _done_out(user: Principal, row: Any, now: datetime) -> DoneOut:
    return DoneOut(id=row.id, done_by=row.done_by_name, done_at=row.done_at, result=row.result, note=row.note,
                   undoable=_undoable(user, row, now))


def hygiene_today(conn: Connection, user: Principal, today: date, now: datetime) -> TodayOut:
    rows = _task_rows(conn, user.pid, hygiene_task.c.active.is_(True))
    if not rows:
        return TodayOut(day=today, open=0, items=[])
    is_open = open_days(conn, user.pid, today - timedelta(days=400), today)
    current = [(r, last_due(_rhythm_of(r), today, is_open)) for r in rows]
    current = [(r, d) for r, d in current if d is not None]
    days = {d for _, d in current}
    proofs = {
        (p.task_id, p.due_on): p
        for p in conn.execute(
            select(hygiene_task_done).where(hygiene_task_done.c.practice_id == user.pid, hygiene_task_done.c.due_on.in_(days))
        )
    } if days else {}
    items = []
    for r, due_on in current:
        proof = proofs.get((r.id, due_on))
        if proof is not None and due_on != today and proof.done_at.astimezone(TUNIS).date() != today:
            continue  # done on an earlier day: nothing to show today
        state: State = "done" if proof is not None else "due" if due_on == today else "overdue"
        items.append(TodayItem(
            task_id=r.id, title=r.title, equipment_name=r.equipment_name, frequency=r.frequency,
            instructions=r.instructions, due_on=due_on, state=state,
            done=_done_out(user, proof, now) if proof is not None else None,
        ))
    order = {"overdue": 0, "due": 1, "done": 2}
    items.sort(key=lambda i: (order[i.state], i.due_on, i.title.lower()))
    return TodayOut(day=today, open=sum(1 for i in items if i.state != "done"), items=items)


def open_count(conn: Connection, user: Principal, today: date, now: datetime) -> int:
    """Overdue and due tasks – the navigation badge."""
    return hygiene_today(conn, user, today, now).open


@router.get("/today")
def today_list(user: StaffUser, ctx: Ctx, conn: Conn) -> TodayOut:
    return hygiene_today(conn, user, today_tunis(ctx.clock), ctx.clock.now())


class DoneIn(ApiModel):
    due_on: date | None = None
    result: Result = "ok"
    note: Note = ""


@router.post("/tasks/{task_id}/done", status_code=201)
def tick_task(task_id: int, body: DoneIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> TodayItem:
    row = _task(conn, user.pid, task_id)
    if not row.active:
        raise unprocessable("Cette tâche est désactivée.", code="task_inactive")
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    current = last_due(_rhythm_of(row), today, open_days(conn, user.pid, today - timedelta(days=400), today))
    if current is None or (body.due_on is not None and body.due_on != current):
        raise unprocessable("Cette échéance n'est pas à faire maintenant.", code="not_due")
    proof = _write(
        conn,
        insert(hygiene_task_done)
        .values(practice_id=user.pid, task_id=task_id, due_on=current, done_by=user.user_id, done_by_name=user.name[:120],
                done_at=now, result=body.result, note=body.note)
        .returning(hygiene_task_done),
        "hygiene_task_done_once",
        lambda: conflict("Déjà fait.", code="already_done"),
    ).one()
    return TodayItem(task_id=row.id, title=row.title, equipment_name=row.equipment_name, frequency=row.frequency,
                     instructions=row.instructions, due_on=current, state="done", done=_done_out(user, proof, now))


@router.delete("/done/{done_id}", status_code=204)
def undo(done_id: int, user: StaffWriter, ctx: Ctx, conn: Conn) -> Response:
    row = conn.execute(
        select(hygiene_task_done, hygiene_task.c.title)
        .select_from(hygiene_task_done.join(hygiene_task, hygiene_task.c.id == hygiene_task_done.c.task_id))
        .where(hygiene_task_done.c.id == done_id, hygiene_task_done.c.practice_id == user.pid)
    ).first()
    if row is None:
        raise not_found()
    now = ctx.clock.now()
    if not _undoable(user, row, now):
        if row.done_by == user.user_id:
            raise forbidden("Seule la personne titulaire peut annuler après 15 minutes.", code="undo_too_late")
        raise forbidden()
    audit.record(conn, user, entity="hygiene_task_done", entity_id=done_id, action="delete", now=now,
                 before={"task": row.title, "dueOn": row.due_on, "doneBy": row.done_by_name, "doneAt": row.done_at,
                         "result": row.result, "note": row.note})
    conn.execute(delete(hygiene_task_done).where(hygiene_task_done.c.id == done_id))
    return Response(status_code=204)


# --- history ----------------------------------------------------------------------------------------------------


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
    status: Literal["done", "missed", "due"]
    late: bool
    done: HistoryDone | None


class HistoryOut(ApiModel):
    from_: date = Field(alias="from")
    to: date
    rows: list[HistoryRow]


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
    conditions = [hygiene_task.c.equipment_id == equipment_id] if equipment_id is not None else []
    tasks = {r.id: r for r in _task_rows(conn, user.pid, *conditions)}
    proofs = conn.execute(
        select(hygiene_task_done).where(
            hygiene_task_done.c.practice_id == user.pid, hygiene_task_done.c.due_on >= first,
            hygiene_task_done.c.due_on <= last, hygiene_task_done.c.task_id.in_(list(tasks) or [0]),
        )
    ).all()
    by_key = {(p.task_id, p.due_on): p for p in proofs}
    keys = set(by_key)
    end = min(last, today)
    if tasks and end >= first:
        is_open = open_days(conn, user.pid, first, end)
        for r in tasks.values():
            if r.active:
                keys |= {(r.id, d) for d in occurrences(_rhythm_of(r), first, end, is_open)}
    rows = []
    for task_id, due_on in keys:
        r, proof = tasks[task_id], by_key.get((task_id, due_on))
        status = "done" if proof is not None else "due" if due_on == today else "missed"
        rows.append(HistoryRow(
            due_on=due_on, task_id=task_id, title=r.title, equipment_name=r.equipment_name, status=status,
            late=proof is not None and proof.done_at.astimezone(TUNIS).date() > due_on,
            done=HistoryDone(id=proof.id, done_by=proof.done_by_name, done_at=proof.done_at, result=proof.result,
                             note=proof.note) if proof is not None else None,
        ))
    rows.sort(key=lambda row: (-row.due_on.toordinal(), row.title.lower(), row.task_id))
    return HistoryOut(from_=first, to=last, rows=rows)
