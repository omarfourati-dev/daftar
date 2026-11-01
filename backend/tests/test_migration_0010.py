"""Migration 0010: the hygiene register is written down – every existing proof keeps its row, the gaps of existing tasks
are written at the first read (review H1)."""

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert, select

from daftar.tables import equipment, hygiene_task, hygiene_task_done, hygiene_task_due
from tests.conftest import _alembic


def test_0010_keeps_every_proof_and_writes_the_gaps_later(
    db: Engine, client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., Any],
    auth_headers: Callable[..., Any],
) -> None:
    p = make_practice()
    headers = auth_headers(make_user(p, "assistant"))
    monday = datetime(2026, 10, 26, 7, tzinfo=timezone.utc)
    try:
        with db.begin() as conn:
            command.downgrade(_alembic(conn), "0009")
            gear = conn.execute(insert(equipment).values(practice_id=p.id, name="Fauteuil").returning(equipment.c.id)).scalar_one()
            task = conn.execute(insert(hygiene_task).values(
                practice_id=p.id, title="Purge", equipment_id=gear, frequency="daily", starts_on=date(2026, 10, 26),
                created_at=monday).returning(hygiene_task.c.id)).scalar_one()
            conn.execute(insert(hygiene_task_done).values(practice_id=p.id, task_id=task, due_on=date(2026, 10, 27),
                                                          done_by_name="Nisrine", done_at=monday))
            command.upgrade(_alembic(conn), "head")
        with db.connect() as conn:
            kept = conn.execute(select(hygiene_task_due.c.due_on, hygiene_task_due.c.title, hygiene_task_due.c.equipment_name,
                                       hygiene_task_due.c.status)).all()
        assert [tuple(r) for r in kept] == [(date(2026, 10, 27), "Purge", "Fauteuil", "done")]
        rows = client.get("/api/hygiene/history?from=2026-10-26&to=2026-10-30", headers=headers).json()["rows"]
        assert [(r["dueOn"], r["status"]) for r in rows] == [
            ("2026-10-30", "due"), ("2026-10-29", "missed"), ("2026-10-28", "missed"), ("2026-10-27", "done"),
            ("2026-10-26", "missed")]
    finally:
        with db.begin() as conn:
            command.upgrade(_alembic(conn), "head")
