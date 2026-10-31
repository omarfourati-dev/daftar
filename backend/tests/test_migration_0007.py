"""Migration 0007: 29 DT a month and 290 DT a year – prices changed by hand and written invoices stay as they are."""

from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from alembic import command
from sqlalchemy import Engine, insert, select, update

from daftar.tables import invoice, plan
from tests.conftest import _alembic

NEW = {"pilot": 0, "cabinet_mensuel": 29_000, "cabinet_annuel": 290_000}


def _prices(db: Engine) -> dict[str, int]:
    with db.connect() as conn:
        return dict(conn.execute(select(plan.c.code, plan.c.price_millimes)).all())  # type: ignore[arg-type]


def test_0007_lowers_the_paid_plans_and_keeps_invoices(db: Engine, make_practice: Callable[..., Any]) -> None:
    assert _prices(db) == NEW
    try:
        with db.begin() as conn:
            command.downgrade(_alembic(conn), "0006")
        assert _prices(db) == {"pilot": 0, "cabinet_mensuel": 49_000, "cabinet_annuel": 490_000}

        p = make_practice(status="active", plan_code="cabinet_mensuel")
        with db.begin() as conn:
            conn.execute(insert(invoice).values(practice_id=p.id, number="DAF-2026-0001", plan_code="cabinet_mensuel",
                                                period_start=date(2026, 11, 1), period_end=date(2026, 11, 30),
                                                amount_millimes=49_000, due_on=date(2026, 11, 1),
                                                created_at=datetime(2026, 10, 30, 8, tzinfo=timezone.utc)))
            conn.execute(update(plan).where(plan.c.code == "cabinet_annuel").values(price_millimes=450_000))  # by hand
            command.upgrade(_alembic(conn), "head")
        assert _prices(db) == {"pilot": 0, "cabinet_mensuel": 29_000, "cabinet_annuel": 450_000}
        with db.connect() as conn:
            assert conn.execute(select(invoice.c.amount_millimes)).scalar_one() == 49_000  # an invoice is a document
    finally:  # the plans are reference data, not emptied between tests: leave them as every other test expects
        with db.begin() as conn:
            command.upgrade(_alembic(conn), "head")
            for code, price in NEW.items():
                conn.execute(update(plan).where(plan.c.code == code).values(price_millimes=price))
