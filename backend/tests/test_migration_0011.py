"""Migration 0011: existing material costs become the moving average of what is in stock (review H2/M1)."""

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from alembic import command
from sqlalchemy import Engine, insert, select

from daftar.tables import stock_movement, stock_product, stock_receipt, stock_receipt_line
from tests.conftest import _alembic


def test_0011_computes_the_moving_average_of_existing_movements(db: Engine, make_practice: Callable[..., Any]) -> None:
    p = make_practice()
    start = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
    try:
        with db.begin() as conn:
            command.downgrade(_alembic(conn), "0010")
            gloves = conn.execute(insert(stock_product).values(practice_id=p.id, name="Gants").returning(stock_product.c.id)).scalar_one()

            def receive(at: datetime, quantity: int, price: int) -> None:
                receipt = conn.execute(insert(stock_receipt).values(practice_id=p.id, received_on=at.date(), created_at=at)
                                       .returning(stock_receipt.c.id)).scalar_one()
                line = conn.execute(insert(stock_receipt_line).values(practice_id=p.id, receipt_id=receipt, product_id=gloves,
                                                                      quantity=quantity, unit_price_millimes=price)
                                    .returning(stock_receipt_line.c.id)).scalar_one()
                conn.execute(insert(stock_movement).values(practice_id=p.id, product_id=gloves, kind="receipt", quantity=quantity,
                                                           receipt_line_id=line, unit_cost_millimes=price, created_at=at))

            receive(start, 100, 12_000)
            conn.execute(insert(stock_movement).values(practice_id=p.id, product_id=gloves, kind="use", quantity=-100,
                                                       unit_cost_millimes=12_000, created_at=start + timedelta(days=1)))
            receive(start + timedelta(days=2), 10, 18_000)
            late = conn.execute(insert(stock_movement).values(practice_id=p.id, product_id=gloves, kind="use", quantity=-1,
                                                              unit_cost_millimes=12_545, created_at=start + timedelta(days=3))
                                .returning(stock_movement.c.id)).scalar_one()
            command.upgrade(_alembic(conn), "head")
        with db.connect() as conn:
            assert conn.execute(select(stock_product.c.average_cost_millimes)).scalar_one() == 18_000
            assert conn.execute(select(stock_movement.c.unit_cost_millimes).where(stock_movement.c.id == late)).scalar_one() == 18_000
            assert conn.execute(select(stock_receipt.c.received_on).limit(1)).scalar_one() == date(2026, 10, 1)
    finally:
        with db.begin() as conn:
            command.upgrade(_alembic(conn), "head")
