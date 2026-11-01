"""``/api/stock``: products and suppliers of the practice (spec stock-hygiène 3, 4.1, 4.2, 4.4).

Roles (section 3): every staff role reads products, suppliers and "à commander"; assistant and owner set them up;
prices are shown to assistant and owner only (``averageCostMillimes`` is null for a dentist).

- ``GET /products`` → ``[Product]`` by name: the product with its stock (sum of its movements), traffic light
  ``status`` (unreceived / ok / low / empty – :func:`daftar.stock_rules.stock_status`), ``hasHistory``, soonest expiry
  date in stock and its state (expired / soon), the moving average price (:func:`recost`) and the last time it was
  used (the "Sortie" list puts those first).
- ``POST /products`` · ``PATCH /products/{id}`` (the unit is locked once something was recorded: 409 ``unit_in_use``
  – a new product is the way) · ``DELETE /products/{id}`` (only without history, else 409 ``product_in_use`` –
  deactivate it instead) · ``POST /products/starter`` → ``{created}``: the start list of the practice's specialty in
  the user's language, never twice the same name.
- ``GET /suppliers`` → ``[Supplier]`` with the number of products · ``POST`` · ``PATCH /{id}`` · ``DELETE /{id}``
  (only when no product or receipt refers to it, else 409 ``supplier_in_use``).
- ``GET /to-order`` → ``{count, groups:[{supplier|null, items:[{productId, name, unit, quantity, minQuantity,
  suggested}]}]}``: active products whose stock reached their minimum, by supplier (without supplier last); a product
  never delivered, used nor counted is not an order yet.

Changes and deletions of products and suppliers are in the change log (who, when, old → new – :mod:`daftar.audit`).
Names are unique per practice without case (409 ``product_exists`` / ``supplier_exists``).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import Connection, bindparam, delete, exists, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import audit
from .clock import today_tunis
from .db import constraint_name
from .deps import Conn, Ctx, Principal, StaffUser, StaffWriter
from .phone import OptionalPhone
from .problems import ApiError, conflict, forbidden, not_found, unprocessable
from .schemas import ApiModel, Name, TunisDateTime
from .stock_rules import (
    MAX_QUANTITY,
    Category,
    ExpiryState,
    CostMove,
    StockStatus,
    Unit,
    cost_order,
    expiry_state,
    moving_costs,
    needs_order,
    reorder_quantity,
    soonest_expiry,
    starter_items,
    stock_status,
)
from .tables import practice, stock_movement, stock_product, stock_receipt, stock_receipt_line, supplier

router = APIRouter(prefix="/api/stock", tags=["stock"])

#: Roles that set up the stock, enter deliveries and see prices (section 3).
MANAGERS = ("owner", "assistant")
Note = Annotated[str, Field(max_length=500)]
Quantity = Annotated[int, Field(ge=0, le=MAX_QUANTITY, strict=True)]
Ean = Annotated[str, Field(pattern=r"^[0-9]{8,14}$")]


def _manager(user: StaffWriter) -> Principal:
    """Assistant or owner of a practice whose subscription is not suspended (402 first, then 403)."""
    if user.role not in MANAGERS:
        raise forbidden()
    return user


def _manager_reader(user: StaffUser) -> Principal:
    if user.role not in MANAGERS:
        raise forbidden()
    return user


#: Changes products, suppliers, receipts, waste and inventory.
StockManager = Annotated[Principal, Depends(_manager)]
#: Reads what carries prices (receipts).
StockManagerReader = Annotated[Principal, Depends(_manager_reader)]


def sees_prices(user: Principal) -> bool:
    return user.role in MANAGERS


# --- products ---------------------------------------------------------------------------------------------------


class ProductOut(ApiModel):
    id: int
    name: str
    category: Category
    unit: Unit
    supplier_id: int | None
    supplier_name: str | None
    min_quantity: int
    note: str
    ean: str | None
    active: bool
    quantity: int
    status: StockStatus
    #: Something was delivered, used or counted: the unit is locked, deleting means deactivating.
    has_history: bool
    expires_on: date | None
    expiry: ExpiryState | None
    average_cost_millimes: int | None
    last_used_at: TunisDateTime | None


class ProductIn(ApiModel):
    name: Name
    category: Category = "autre"
    unit: Unit = "piece"
    supplier_id: int | None = None
    min_quantity: Quantity = 0
    note: Note = ""
    ean: Ean | None = None
    active: StrictBool = True


class ProductPatch(ApiModel):
    name: Name | None = None
    category: Category | None = None
    unit: Unit | None = None
    supplier_id: int | None = None
    min_quantity: Quantity | None = None
    note: Note | None = None
    ean: Ean | None = None
    active: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> ProductPatch:
        for name in self.model_fields_set - {"supplier_id", "ean"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


def stock_levels(conn: Connection, practice_id: int, product_ids: Sequence[int] | None = None) -> dict[int, int]:
    """Product id → stock (sum of its movements); products without movements are missing (stock 0)."""
    conditions = [stock_movement.c.practice_id == practice_id]
    if product_ids is not None:
        conditions.append(stock_movement.c.product_id.in_(product_ids))
    rows = conn.execute(
        select(stock_movement.c.product_id, func.sum(stock_movement.c.quantity))
        .where(*conditions)
        .group_by(stock_movement.c.product_id)
    ).all()
    return {product_id: int(total) for product_id, total in rows}


def recost(conn: Connection, practice_id: int, product_ids: Sequence[int]) -> None:
    """Computes the costs of these products again from their first movement (review H2/M1): every unit cost of a use,
    loss or count and the product's average today. Called after every change of their movements or receipt lines."""
    if not product_ids:
        return
    rows = conn.execute(
        select(stock_movement.c.id, stock_movement.c.product_id, stock_movement.c.kind, stock_movement.c.quantity,
               stock_movement.c.created_at, stock_movement.c.unit_cost_millimes, stock_receipt_line.c.unit_price_millimes,
               stock_receipt.c.received_on)
        .select_from(
            stock_movement.outerjoin(stock_receipt_line, stock_receipt_line.c.id == stock_movement.c.receipt_line_id)
            .outerjoin(stock_receipt, stock_receipt.c.id == stock_receipt_line.c.receipt_id)
        )
        .where(stock_movement.c.practice_id == practice_id, stock_movement.c.product_id.in_(product_ids))
    ).all()
    by_product: dict[int, list[Any]] = defaultdict(list)
    for row in rows:
        by_product[row.product_id].append(row)
    changed: list[dict[str, Any]] = []
    averages: list[dict[str, Any]] = []
    for product_id in sorted(set(product_ids)):
        moves = sorted(by_product.get(product_id, []), key=lambda r: cost_order(r.id, r.kind, r.created_at, r.received_on))
        costs = moving_costs(CostMove(r.id, r.kind, r.quantity, r.unit_price_millimes) for r in moves)
        changed += [{"mid": r.id, "cost": costs.unit_costs[r.id]} for r in moves
                    if costs.unit_costs[r.id] != r.unit_cost_millimes]
        averages.append({"pid": product_id, "average": costs.average})
    if changed:
        conn.execute(update(stock_movement).where(stock_movement.c.id == bindparam("mid"))
                     .values(unit_cost_millimes=bindparam("cost")), changed)
    conn.execute(update(stock_product).where(stock_product.c.id == bindparam("pid"))
                 .values(average_cost_millimes=bindparam("average")), averages)


def _receipt_lines(
    conn: Connection, practice_id: int, product_ids: Sequence[int] | None
) -> dict[int, list[tuple[int, int | None, date | None]]]:
    conditions = [stock_receipt_line.c.practice_id == practice_id]
    if product_ids is not None:
        conditions.append(stock_receipt_line.c.product_id.in_(product_ids))
    result: dict[int, list[tuple[int, int | None, date | None]]] = defaultdict(list)
    for row in conn.execute(
        select(stock_receipt_line.c.product_id, stock_receipt_line.c.quantity, stock_receipt_line.c.unit_price_millimes,
               stock_receipt_line.c.expires_on).where(*conditions)
    ):
        result[row.product_id].append((row.quantity, row.unit_price_millimes, row.expires_on))
    return result


def load_products(
    conn: Connection, practice_id: int, today: date, *, prices: bool, product_ids: Sequence[int] | None = None
) -> list[ProductOut]:
    conditions = [stock_product.c.practice_id == practice_id]
    if product_ids is not None:
        conditions.append(stock_product.c.id.in_(product_ids))
    rows = conn.execute(
        select(stock_product, supplier.c.name.label("supplier_name"))
        .select_from(stock_product.outerjoin(supplier, supplier.c.id == stock_product.c.supplier_id))
        .where(*conditions)
        .order_by(func.lower(stock_product.c.name), stock_product.c.id)
    ).all()
    levels = stock_levels(conn, practice_id, product_ids)
    lines = _receipt_lines(conn, practice_id, product_ids)
    use_conditions = [stock_movement.c.practice_id == practice_id, stock_movement.c.kind == "use"]
    if product_ids is not None:
        use_conditions.append(stock_movement.c.product_id.in_(product_ids))
    last_used = dict(
        conn.execute(
            select(stock_movement.c.product_id, func.max(stock_movement.c.created_at))
            .where(*use_conditions)
            .group_by(stock_movement.c.product_id)
        ).all()
    )
    result = []
    for row in rows:
        quantity = levels.get(row.id, 0)
        received = row.id in levels  # delivered, used or counted at least once
        own = lines.get(row.id, [])
        expires_on = soonest_expiry(quantity, ((expires, q) for q, _, expires in own))
        result.append(ProductOut(
            id=row.id, name=row.name, category=row.category, unit=row.unit, supplier_id=row.supplier_id,
            supplier_name=row.supplier_name, min_quantity=row.min_quantity, note=row.note, ean=row.ean,
            active=row.active, quantity=quantity, status=stock_status(quantity, row.min_quantity, received=received),
            has_history=received, expires_on=expires_on, expiry=expiry_state(expires_on, today),
            average_cost_millimes=row.average_cost_millimes if prices else None,
            last_used_at=last_used.get(row.id),
        ))
    return result


def product_row(conn: Connection, practice_id: int, product_id: int) -> Any:
    """The product of this practice (404 otherwise)."""
    row = conn.execute(
        select(stock_product).where(stock_product.c.id == product_id, stock_product.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    return row


def check_supplier(conn: Connection, practice_id: int, supplier_id: int | None) -> None:
    if supplier_id is None:
        return
    found = conn.execute(
        select(supplier.c.id).where(supplier.c.id == supplier_id, supplier.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise unprocessable("Ce fournisseur n'existe pas dans le cabinet.", code="invalid_supplier")


def _one_product(conn: Connection, user: Principal, ctx: Ctx, product_id: int) -> ProductOut:
    (out,) = load_products(conn, user.pid, today_tunis(ctx.clock), prices=sees_prices(user), product_ids=[product_id])
    return out


def _write_unique(conn: Connection, statement: Any, constraint: str, error: Callable[[], ApiError]) -> Any:
    """Runs ``statement`` in a savepoint; a duplicate name (``constraint``) becomes ``error()``."""
    try:
        with conn.begin_nested():
            return conn.execute(statement)
    except IntegrityError as exc:
        if constraint_name(exc) == constraint:
            raise error() from exc
        raise


def PRODUCT_EXISTS() -> ApiError:  # noqa: N802 - reads like the constant it stands for
    return conflict("Un produit porte déjà ce nom.", code="product_exists")


def SUPPLIER_EXISTS() -> ApiError:  # noqa: N802
    return conflict("Un fournisseur porte déjà ce nom.", code="supplier_exists")


@router.get("/products")
def list_products(user: StaffUser, ctx: Ctx, conn: Conn) -> list[ProductOut]:
    return load_products(conn, user.pid, today_tunis(ctx.clock), prices=sees_prices(user))


@router.post("/products", status_code=201)
def create_product(body: ProductIn, user: StockManager, ctx: Ctx, conn: Conn) -> ProductOut:
    check_supplier(conn, user.pid, body.supplier_id)
    values = body.model_dump(by_alias=False)
    new_id = _write_unique(
        conn,
        insert(stock_product).values(practice_id=user.pid, created_at=ctx.clock.now(), **values).returning(stock_product.c.id),
        "stock_product_name_key",
        PRODUCT_EXISTS,
    ).scalar_one()
    return _one_product(conn, user, ctx, new_id)


#: Field → key in the change log (the supplier by its name).
PRODUCT_LOG = {"name": "name", "category": "category", "unit": "unit", "supplier": "supplier",
               "min_quantity": "minQuantity", "note": "note", "ean": "ean", "active": "active"}


def _has_history(conn: Connection, product_id: int) -> bool:
    return bool(conn.execute(
        select(or_(exists().where(stock_movement.c.product_id == product_id),
                   exists().where(stock_receipt_line.c.product_id == product_id)))
    ).scalar_one())


def _supplier_name(conn: Connection, supplier_id: int | None) -> str | None:
    if supplier_id is None:
        return None
    return conn.execute(select(supplier.c.name).where(supplier.c.id == supplier_id)).scalar_one_or_none()


@router.patch("/products/{product_id}")
def patch_product(product_id: int, body: ProductPatch, user: StockManager, ctx: Ctx, conn: Conn) -> ProductOut:
    row = product_row(conn, user.pid, product_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    if "supplier_id" in values:
        check_supplier(conn, user.pid, values["supplier_id"])
    if values.get("unit", row.unit) != row.unit and _has_history(conn, product_id):
        raise conflict("Ce produit a déjà des mouvements : son unité ne change plus. Créez un nouveau produit.",
                       code="unit_in_use")
    old = {k: getattr(row, k) for k in PRODUCT_LOG if k != "supplier"} | {"supplier": _supplier_name(conn, row.supplier_id)}
    new = values | ({"supplier": _supplier_name(conn, values["supplier_id"])} if "supplier_id" in values else {})
    before, after = audit.diff(old, new, PRODUCT_LOG)
    if after:
        _write_unique(conn, update(stock_product).where(stock_product.c.id == product_id).values(**values),
                      "stock_product_name_key", PRODUCT_EXISTS)
        audit.record(conn, user, entity="stock_product", entity_id=product_id, action="update", now=ctx.clock.now(),
                     before={"product": row.name, **before}, after=after)
    return _one_product(conn, user, ctx, product_id)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, user: StockManager, ctx: Ctx, conn: Conn) -> Response:
    row = product_row(conn, user.pid, product_id)
    if _has_history(conn, product_id):
        raise conflict("Ce produit a un historique : désactivez-le plutôt.", code="product_in_use")
    audit.record(conn, user, entity="stock_product", entity_id=product_id, action="delete", now=ctx.clock.now(),
                 before={"name": row.name, "category": row.category, "unit": row.unit})
    conn.execute(delete(stock_product).where(stock_product.c.id == product_id))
    return Response(status_code=204)


class StarterOut(ApiModel):
    created: int


@router.post("/products/starter")
def create_starter_list(user: StockManager, ctx: Ctx, conn: Conn) -> StarterOut:
    specialty = conn.execute(select(practice.c.specialty).where(practice.c.id == user.pid)).scalar_one()
    existing = {
        name.lower()
        for name in conn.execute(select(stock_product.c.name).where(stock_product.c.practice_id == user.pid)).scalars()
    }
    rows = []
    for item in starter_items(specialty):
        name = item.name_ar if user.lang == "ar" else item.name_fr
        if name.lower() in existing:
            continue
        existing.add(name.lower())
        rows.append({"practice_id": user.pid, "name": name, "category": item.category, "unit": item.unit,
                     "min_quantity": item.min_quantity, "created_at": ctx.clock.now()})
    if rows:
        conn.execute(insert(stock_product), rows)
    return StarterOut(created=len(rows))


# --- suppliers --------------------------------------------------------------------------------------------------


class SupplierOut(ApiModel):
    id: int
    name: str
    phone: str | None
    whatsapp: str | None
    note: str
    active: bool
    products: int


class SupplierIn(ApiModel):
    name: Name
    phone: OptionalPhone = None
    whatsapp: OptionalPhone = None
    note: Note = ""
    active: StrictBool = True


class SupplierPatch(ApiModel):
    name: Name | None = None
    phone: OptionalPhone = None
    whatsapp: OptionalPhone = None
    note: Note | None = None
    active: StrictBool | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> SupplierPatch:
        for name in self.model_fields_set - {"phone", "whatsapp"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


def _suppliers(conn: Connection, practice_id: int, supplier_id: int | None = None) -> list[SupplierOut]:
    count = (
        select(func.count())
        .where(stock_product.c.supplier_id == supplier.c.id)
        .scalar_subquery()
    )
    conditions = [supplier.c.practice_id == practice_id]
    if supplier_id is not None:
        conditions.append(supplier.c.id == supplier_id)
    rows = conn.execute(
        select(supplier, count.label("products")).where(*conditions).order_by(func.lower(supplier.c.name), supplier.c.id)
    ).all()
    return [SupplierOut.model_validate(r, from_attributes=True) for r in rows]


def _supplier(conn: Connection, practice_id: int, supplier_id: int) -> SupplierOut:
    found = _suppliers(conn, practice_id, supplier_id)
    if not found:
        raise not_found()
    return found[0]


@router.get("/suppliers")
def list_suppliers(user: StaffUser, conn: Conn) -> list[SupplierOut]:
    return _suppliers(conn, user.pid)


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn, user: StockManager, ctx: Ctx, conn: Conn) -> SupplierOut:
    new_id = _write_unique(
        conn,
        insert(supplier).values(practice_id=user.pid, created_at=ctx.clock.now(), **body.model_dump(by_alias=False))
        .returning(supplier.c.id),
        "supplier_name_key",
        SUPPLIER_EXISTS,
    ).scalar_one()
    return _supplier(conn, user.pid, new_id)


SUPPLIER_LOG = {"name": "name", "phone": "phone", "whatsapp": "whatsapp", "note": "note", "active": "active"}


@router.patch("/suppliers/{supplier_id}")
def patch_supplier(supplier_id: int, body: SupplierPatch, user: StockManager, ctx: Ctx, conn: Conn) -> SupplierOut:
    current = _supplier(conn, user.pid, supplier_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    before, after = audit.diff(current.model_dump(by_alias=False), values, SUPPLIER_LOG)
    if after:
        _write_unique(conn, update(supplier).where(supplier.c.id == supplier_id).values(**values), "supplier_name_key",
                      SUPPLIER_EXISTS)
        audit.record(conn, user, entity="supplier", entity_id=supplier_id, action="update", now=ctx.clock.now(),
                     before={"supplier": current.name, **before}, after=after)
    return _supplier(conn, user.pid, supplier_id)


@router.delete("/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, user: StockManager, ctx: Ctx, conn: Conn) -> Response:
    current = _supplier(conn, user.pid, supplier_id)
    used = conn.execute(
        select(
            or_(
                exists().where(stock_product.c.supplier_id == supplier_id),
                exists().where(stock_receipt.c.supplier_id == supplier_id),
            )
        )
    ).scalar_one()
    if used:
        raise conflict("Ce fournisseur est utilisé : désactivez-le plutôt.", code="supplier_in_use")
    audit.record(conn, user, entity="supplier", entity_id=supplier_id, action="delete", now=ctx.clock.now(),
                 before={"name": current.name, "phone": current.phone, "whatsapp": current.whatsapp})
    conn.execute(delete(supplier).where(supplier.c.id == supplier_id))
    return Response(status_code=204)


# --- à commander ------------------------------------------------------------------------------------------------


class OrderSupplier(ApiModel):
    id: int
    name: str
    phone: str | None
    whatsapp: str | None


class OrderItem(ApiModel):
    product_id: int
    name: str
    unit: Unit
    quantity: int
    min_quantity: int
    suggested: int


class OrderGroup(ApiModel):
    supplier: OrderSupplier | None
    items: list[OrderItem]


class ToOrderOut(ApiModel):
    count: int
    groups: list[OrderGroup]


def _with_threshold(conn: Connection, practice_id: int) -> list[Any]:
    return conn.execute(
        select(stock_product.c.id, stock_product.c.name, stock_product.c.unit, stock_product.c.min_quantity,
               stock_product.c.supplier_id)
        .where(stock_product.c.practice_id == practice_id, stock_product.c.active.is_(True),
               stock_product.c.min_quantity > 0)
        .order_by(func.lower(stock_product.c.name), stock_product.c.id)
    ).all()


def to_order_count(conn: Connection, practice_id: int) -> int:
    """How many products are "à commander" – for the dashboard card and the navigation badge."""
    candidates = _with_threshold(conn, practice_id)
    if not candidates:
        return 0
    levels = stock_levels(conn, practice_id, [c.id for c in candidates])
    return sum(1 for c in candidates
               if needs_order(stock=levels.get(c.id, 0), min_quantity=c.min_quantity, active=True, received=c.id in levels))


@router.get("/to-order")
def to_order(user: StaffUser, conn: Conn) -> ToOrderOut:
    candidates = _with_threshold(conn, user.pid)
    levels = stock_levels(conn, user.pid, [c.id for c in candidates]) if candidates else {}
    by_supplier: dict[int | None, list[OrderItem]] = defaultdict(list)
    for c in candidates:
        stock = levels.get(c.id, 0)
        if needs_order(stock=stock, min_quantity=c.min_quantity, active=True, received=c.id in levels):
            by_supplier[c.supplier_id].append(OrderItem(
                product_id=c.id, name=c.name, unit=c.unit, quantity=stock, min_quantity=c.min_quantity,
                suggested=reorder_quantity(stock=stock, min_quantity=c.min_quantity),
            ))
    known = [sid for sid in by_supplier if sid is not None]
    suppliers = {
        row.id: OrderSupplier(id=row.id, name=row.name, phone=row.phone, whatsapp=row.whatsapp)
        for row in conn.execute(
            select(supplier.c.id, supplier.c.name, supplier.c.phone, supplier.c.whatsapp)
            .where(supplier.c.practice_id == user.pid, supplier.c.id.in_(known))
        )
    } if known else {}
    groups = sorted(
        (OrderGroup(supplier=suppliers[sid], items=items) for sid, items in by_supplier.items() if sid in suppliers),
        key=lambda g: (g.supplier.name.lower() if g.supplier else ""),
    )
    loose = [item for sid, items in by_supplier.items() if sid not in suppliers for item in items]
    if loose:
        groups.append(OrderGroup(supplier=None, items=loose))
    return ToOrderOut(count=sum(len(g.items) for g in groups), groups=groups)
