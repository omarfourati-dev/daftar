"""Migration 0009 (hygiene): equipment, tasks and their proofs stay in their practice; one proof per due date."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.exc import IntegrityError

from daftar.db import constraint_name
from daftar.tables import equipment, hygiene_task, hygiene_task_done

Factory = Callable[..., Any]


def refused(db: Engine, statement: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, db.begin() as conn:
        conn.execute(statement)
    return constraint_name(caught.value)


def _one(db: Engine, table: Any, **values: Any) -> Any:
    with db.begin() as conn:
        return conn.execute(insert(table).values(**values).returning(table)).one()


def test_tasks_have_a_consistent_rhythm(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    autoclave = _one(db, equipment, practice_id=p.id, name="Autoclave", kind="autoclave")
    assert (autoclave.serial_number, autoclave.active) == ("", True)
    assert refused(db, insert(equipment).values(practice_id=p.id, name="AUTOCLAVE")) == "equipment_name_key"
    refused(db, insert(equipment).values(practice_id=p.id, name="Four", kind="four"))
    base = {"practice_id": p.id, "title": "Test", "starts_on": date(2026, 10, 26)}
    _one(db, hygiene_task, **base, frequency="weekly", weekday=1, equipment_id=autoclave.id)
    _one(db, hygiene_task, **base, frequency="every_n_days", interval_days=10)
    for values in ({"frequency": "weekly"}, {"frequency": "daily", "weekday": 2}, {"frequency": "every_n_days"},
                   {"frequency": "every_n_days", "interval_days": 1}, {"frequency": "hourly"},
                   {"frequency": "weekly", "weekday": 8}):
        assert refused(db, insert(hygiene_task).values(**base, **values)), values


def test_one_proof_per_task_and_day_and_never_across_practices(db: Engine, make_practice: Factory, clock: Any) -> None:
    mine, other = make_practice(), make_practice()
    task = _one(db, hygiene_task, practice_id=mine.id, title="Purge", frequency="daily", starts_on=date(2026, 10, 1))
    proof = {"task_id": task.id, "due_on": date(2026, 10, 30), "done_at": clock.now()}
    done = _one(db, hygiene_task_done, practice_id=mine.id, **proof, done_by_name="Nisrine")
    assert (done.result, done.note) == ("ok", "")
    assert refused(db, insert(hygiene_task_done).values(practice_id=mine.id, **proof)) == "hygiene_task_done_once"
    assert refused(db, insert(hygiene_task_done).values(practice_id=other.id, **{**proof, "due_on": date(2026, 10, 29)})) == (
        "hygiene_task_done_task_fkey")
    refused(db, insert(hygiene_task_done).values(practice_id=mine.id, **{**proof, "due_on": date(2026, 10, 28)}, result="bof"))
    assert refused(db, delete(hygiene_task).where(hygiene_task.c.id == task.id)) == "hygiene_task_done_task_fkey"
    with db.begin() as conn:  # equipment goes, its tasks stay
        gear = conn.execute(insert(equipment).values(practice_id=mine.id, name="Aspiration").returning(equipment.c.id)).scalar_one()
        conn.execute(hygiene_task.update().where(hygiene_task.c.id == task.id).values(equipment_id=gear))
        conn.execute(delete(equipment).where(equipment.c.id == gear))
        assert conn.execute(select(hygiene_task.c.equipment_id).where(hygiene_task.c.id == task.id)).scalar_one() is None
