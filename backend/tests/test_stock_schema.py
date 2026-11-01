"""Migration 0008 (stock and change log): constraints that keep stocks believable and tenants apart."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from daftar.db import constraint_name
from daftar.tables import audit_log, stock_movement, stock_product, stock_receipt, stock_receipt_line, supplier

Factory = Callable[..., Any]


def refused(db: Engine, statement: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, db.begin() as conn:
        conn.execute(statement)
    return constraint_name(caught.value)


def _one(db: Engine, table: Any, **values: Any) -> Any:
    with db.begin() as conn:
        return conn.execute(insert(table).values(**values).returning(table)).one()


def test_products_and_suppliers_have_defaults_and_unique_names(db: Engine, make_practice: Factory) -> None:
    p, other = make_practice(), make_practice()
    sup = _one(db, supplier, practice_id=p.id, name="Dentalia Sfax", phone="+21674000000")
    assert (sup.active, sup.note, sup.whatsapp) == (True, "", None)
    gloves = _one(db, stock_product, practice_id=p.id, name="Gants", supplier_id=sup.id)
    assert (gloves.category, gloves.unit, gloves.min_quantity, gloves.active, gloves.ean) == ("autre", "piece", 0, True, None)
    assert refused(db, insert(stock_product).values(practice_id=p.id, name="GANTS")) == "stock_product_name_key"
    _one(db, stock_product, practice_id=other.id, name="Gants")  # another practice may have the same name
    assert refused(db, insert(supplier).values(practice_id=p.id, name="dentalia sfax")) == "supplier_name_key"
    for values in ({"category": "jouets"}, {"unit": "kilo"}, {"min_quantity": -1}, {"ean": "12AB"}, {"name": ""}):
        refused(db, insert(stock_product).values(practice_id=p.id, **{"name": "X", **values}))
    refused(db, insert(supplier).values(practice_id=p.id, name="Y", whatsapp="20123456"))


def test_receipt_lines_and_movements_stay_in_their_practice(db: Engine, make_practice: Factory, clock: Any) -> None:
    mine, other = make_practice(), make_practice()
    product = _one(db, stock_product, practice_id=mine.id, name="Gants")
    foreign = _one(db, stock_product, practice_id=other.id, name="Gants")
    receipt = _one(db, stock_receipt, practice_id=mine.id, received_on=date(2026, 10, 30))
    foreign_receipt = _one(db, stock_receipt, practice_id=other.id, received_on=date(2026, 10, 30))
    assert refused(db, insert(stock_receipt_line).values(practice_id=mine.id, receipt_id=receipt.id, product_id=foreign.id,
                                                         quantity=1)) == "stock_receipt_line_product_fkey"
    assert refused(db, insert(stock_receipt_line).values(practice_id=mine.id, receipt_id=foreign_receipt.id,
                                                         product_id=product.id, quantity=1)) == "stock_receipt_line_receipt_fkey"
    assert refused(db, insert(stock_movement).values(practice_id=mine.id, product_id=foreign.id, kind="use",
                                                     quantity=-1)) == "stock_movement_product_fkey"


def test_movement_kinds_have_their_sign(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    product = _one(db, stock_product, practice_id=p.id, name="Gants")
    receipt = _one(db, stock_receipt, practice_id=p.id, received_on=date(2026, 10, 30))
    line = _one(db, stock_receipt_line, practice_id=p.id, receipt_id=receipt.id, product_id=product.id, quantity=10,
                unit_price_millimes=12_500, lot="L1", expires_on=date(2027, 1, 1))
    base = {"practice_id": p.id, "product_id": product.id}
    _one(db, stock_movement, **base, kind="receipt", quantity=10, receipt_line_id=line.id)
    for values in (
        {"kind": "receipt", "quantity": 10},  # a receipt movement comes from a line
        {"kind": "receipt", "quantity": -1, "receipt_line_id": line.id},
        {"kind": "use", "quantity": 1},
        {"kind": "waste", "quantity": 2},
        {"kind": "adjust", "quantity": 3},  # an inventory correction needs a reason
        {"kind": "adjust", "quantity": 0, "reason": "Inventaire"},
        {"kind": "lost", "quantity": -1},
    ):
        refused(db, insert(stock_movement).values(**base, **values))
    _one(db, stock_movement, **base, kind="use", quantity=-2, unit_cost_millimes=12_500)
    _one(db, stock_movement, **base, kind="adjust", quantity=-1, reason="Inventaire du 30/10")
    with db.connect() as conn:
        assert conn.execute(select(func.sum(stock_movement.c.quantity))).scalar_one() == 7
    assert refused(db, insert(stock_movement).values(**base, kind="receipt", quantity=1,
                                                     receipt_line_id=line.id)) == "stock_movement_line_key"
    refused(db, insert(stock_receipt_line).values(practice_id=p.id, receipt_id=receipt.id, product_id=product.id, quantity=0))


def test_a_product_with_history_cannot_be_deleted_but_a_receipt_takes_its_lines_and_movements(
    db: Engine, make_practice: Factory
) -> None:
    p = make_practice()
    product = _one(db, stock_product, practice_id=p.id, name="Gants")
    receipt = _one(db, stock_receipt, practice_id=p.id, received_on=date(2026, 10, 30))
    line = _one(db, stock_receipt_line, practice_id=p.id, receipt_id=receipt.id, product_id=product.id, quantity=10)
    _one(db, stock_movement, practice_id=p.id, product_id=product.id, kind="receipt", quantity=10, receipt_line_id=line.id)
    assert refused(db, delete(stock_product).where(stock_product.c.id == product.id)) in (
        "stock_receipt_line_product_fkey", "stock_movement_product_fkey")
    with db.begin() as conn:
        conn.execute(delete(stock_receipt).where(stock_receipt.c.id == receipt.id))
        assert conn.execute(select(func.count()).select_from(stock_receipt_line)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(stock_movement)).scalar_one() == 0
        conn.execute(delete(stock_product).where(stock_product.c.id == product.id))


def test_audit_log_entries(db: Engine, make_practice: Factory, make_user: Factory) -> None:
    p = make_practice()
    owner = make_user(p, "owner", name="Dr. Owner")
    row = _one(db, audit_log, practice_id=p.id, user_id=owner.id, user_name="Dr. Owner", entity="stock_receipt",
               entity_id=7, action="delete", before={"lines": 2}, reason="Doublon")
    assert (row.after, row.reason) == (None, "Doublon")
    refused(db, insert(audit_log).values(practice_id=p.id, entity="Stock Receipt", entity_id=1, action="delete"))
    refused(db, insert(audit_log).values(practice_id=p.id, entity="stock_receipt", entity_id=1, action="drop"))
