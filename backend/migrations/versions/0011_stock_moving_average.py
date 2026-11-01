"""Material costs follow corrections (review H2/M1 of stock-hygiène): the moving average of what is in stock.

- ``stock_product.average_cost_millimes``: the product's moving average today (NULL without any price);
- the unit costs of the existing uses, losses and inventory counts are computed again with the moving average, in
  the order the movements happened (a delivery typed in later counts from the end of its delivery day).

The rule is copied here as it stood on 01.11.2026 (the app's :mod:`daftar.stock_rules` may change later; a migration
must not). Additive and safe on the live database.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-01
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TUNIS = ZoneInfo("Africa/Tunis")

UPGRADE = """
ALTER TABLE stock_product ADD COLUMN average_cost_millimes BIGINT NULL
    CHECK (average_cost_millimes BETWEEN 0 AND 100000000);
"""

MOVEMENTS = """
SELECT m.id, m.product_id, m.kind, m.quantity, m.created_at, m.unit_cost_millimes, l.unit_price_millimes, r.received_on
FROM stock_movement m
LEFT JOIN stock_receipt_line l ON l.id = m.receipt_line_id
LEFT JOIN stock_receipt r ON r.id = l.receipt_id
"""


def _order(row: Any) -> tuple[datetime, int]:
    at = row.created_at
    received_on: date | None = row.received_on
    if row.kind == "receipt" and received_on is not None and received_on < at.astimezone(TUNIS).date():
        at = datetime.combine(received_on + timedelta(days=1), time(0), tzinfo=TUNIS)
    return (at, row.id)


def _costs(rows: list[Any]) -> tuple[dict[int, int | None], int | None]:
    unit_costs: dict[int, int | None] = {}
    average: int | None = None
    stock = 0
    waiting: list[int] = []
    for row in sorted(rows, key=_order):
        if row.kind == "receipt":
            price = row.unit_price_millimes
            unit_costs[row.id] = price
            if price is not None:
                base = max(stock, 0)
                first = average is None
                average = price if average is None else (2 * (base * average + row.quantity * price) + base + row.quantity) // (
                    2 * (base + row.quantity))
                if first:
                    unit_costs.update(dict.fromkeys(waiting, average))
                    waiting.clear()
        else:
            unit_costs[row.id] = average
            if average is None:
                waiting.append(row.id)
        stock += row.quantity
    return unit_costs, average


def upgrade() -> None:
    op.execute(UPGRADE)
    conn = op.get_bind()
    by_product: dict[int, list[Any]] = defaultdict(list)
    for row in conn.execute(sa.text(MOVEMENTS)):
        by_product[row.product_id].append(row)
    for product_id, rows in by_product.items():
        unit_costs, average = _costs(rows)
        for row in rows:
            if row.kind != "receipt" and unit_costs[row.id] != row.unit_cost_millimes:
                conn.execute(sa.text("UPDATE stock_movement SET unit_cost_millimes = :c WHERE id = :id"),
                             {"c": unit_costs[row.id], "id": row.id})
        conn.execute(sa.text("UPDATE stock_product SET average_cost_millimes = :a WHERE id = :id"),
                     {"a": average, "id": product_id})


def downgrade() -> None:
    op.execute("ALTER TABLE stock_product DROP COLUMN IF EXISTS average_cost_millimes")
