"""``/api/stock``: deliveries, use, waste, inventory and the owner's corrections (spec stock-hygiène 3, 4.1, 4.2, 8).

- ``POST /receipts {receivedOn?, supplierId?, reference?, note?, lines:[{productId, quantity, unitPriceMillimes?, lot?,
  expiresOn?}]}`` (assistant, owner) → 201 ``Receipt``: one ``receipt`` movement per line; a product without a
  default supplier learns the one of its first delivery. Not in the future (422 ``day_in_future``).
- ``GET /receipts?limit=&offset=`` · ``GET /receipts/{id}`` (assistant, owner – receipts carry prices).
- ``DELETE /receipts/{id} {reason}`` (owner) → 204: the receipt, its lines and their movements go; the change log
  keeps a copy (:mod:`daftar.audit`).
- ``PATCH /receipts/{id}/lines/{lineId} {quantity?, unitPriceMillimes?, reason}`` (owner) → the corrected ``Receipt``
  (a mistyped price or quantity – no need to delete and type the delivery again); logged old → new with the reason.
- ``POST /movements {productId, kind: use|waste, quantity, serviceId?, appointmentId?, reason?}`` → 201
  ``{movement, product}``. Every staff role records a use (3 taps at the desk or from an appointment – the
  appointment's act is taken over when none is given); waste is for assistant and owner. A use may take the stock
  below zero (the material was used); the product then shows ``empty`` with its negative quantity, so the practice
  counts it. The movement's unit cost is the moving average of that moment (:func:`daftar.stock.recost` – computed
  again whenever an earlier receipt or movement of the product changes, so the material cost follows corrections).
- ``GET /movements?productId=&appointmentId=&limit=`` → ``[Movement]`` newest first (costs only for assistant/owner),
  with the act in both languages and, for a receipt, its line and delivery day.
- ``DELETE /movements/{id} {reason}`` (owner) → 204, logged; a receipt movement goes with its receipt only (409
  ``receipt_movement``).
- ``POST /inventory {reason, counts:[{productId, counted}]}`` (assistant, owner) → ``{adjusted, products}``: one
  ``adjust`` movement with the reason per product whose count differs from the stock.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import Field, model_validator
from sqlalchemy import Connection, delete, insert, select, update

from . import audit
from .clock import today_tunis
from .deps import Conn, Ctx, OwnerWriter, StaffUser, StaffWriter
from .money import Millimes
from .problems import conflict, forbidden, not_found, unprocessable
from .schemas import ApiModel, TunisDateTime
from .stock import (
    MANAGERS,
    Note,
    ProductOut,
    StockManager,
    StockManagerReader,
    check_supplier,
    load_products,
    recost,
    sees_prices,
    stock_levels,
)
from .stock_rules import MAX_QUANTITY, Unit
from .tables import (
    app_user,
    appointment,
    patient,
    service,
    stock_movement,
    stock_product,
    stock_receipt,
    stock_receipt_line,
    supplier,
)

router = APIRouter(prefix="/api/stock", tags=["stock"])

Count = Annotated[int, Field(ge=1, le=MAX_QUANTITY, strict=True)]
Reason = Annotated[str, Field(max_length=300)]
RequiredReason = Annotated[str, Field(min_length=1, max_length=300)]
MovementKind = Literal["receipt", "use", "adjust", "waste"]
MAX_LINES = 60


class ReasonIn(ApiModel):
    reason: RequiredReason


def _products(conn: Connection, practice_id: int, ids: set[int], *, active_only: bool) -> dict[int, Any]:
    """The products of this practice by id – 422 ``invalid_product`` for an unknown one (or one of another practice),
    ``product_inactive`` for a deactivated one when ``active_only``."""
    rows = {
        r.id: r
        for r in conn.execute(
            select(stock_product.c.id, stock_product.c.name, stock_product.c.unit, stock_product.c.active)
            .where(stock_product.c.practice_id == practice_id, stock_product.c.id.in_(ids))
        )
    }
    if set(rows) != ids:
        raise unprocessable("Produit introuvable dans le cabinet.", code="invalid_product")
    if active_only and not all(r.active for r in rows.values()):
        raise unprocessable("Ce produit est désactivé.", code="product_inactive")
    return rows


# --- receipts ---------------------------------------------------------------------------------------------------


class ReceiptLineIn(ApiModel):
    product_id: int
    quantity: Count
    unit_price_millimes: Millimes | None = None
    lot: Annotated[str, Field(max_length=60)] = ""
    expires_on: date | None = None


class ReceiptIn(ApiModel):
    received_on: date | None = None
    supplier_id: int | None = None
    reference: Annotated[str, Field(max_length=60)] = ""
    note: Note = ""
    lines: Annotated[list[ReceiptLineIn], Field(min_length=1, max_length=MAX_LINES)]


class ReceiptLineOut(ApiModel):
    id: int
    product_id: int
    product_name: str
    unit: Unit
    quantity: int
    unit_price_millimes: int | None
    lot: str
    expires_on: date | None


class ReceiptOut(ApiModel):
    id: int
    received_on: date
    supplier_id: int | None
    supplier_name: str | None
    reference: str
    note: str
    created_by: str | None
    created_at: TunisDateTime
    lines: list[ReceiptLineOut]
    total_millimes: int


def load_receipts(conn: Connection, practice_id: int, *conditions: Any, limit: int = 30, offset: int = 0) -> list[ReceiptOut]:
    heads = conn.execute(
        select(stock_receipt, supplier.c.name.label("supplier_name"), app_user.c.name.label("created_by_name"))
        .select_from(
            stock_receipt.outerjoin(supplier, supplier.c.id == stock_receipt.c.supplier_id)
            .outerjoin(app_user, app_user.c.id == stock_receipt.c.created_by)
        )
        .where(stock_receipt.c.practice_id == practice_id, *conditions)
        .order_by(stock_receipt.c.received_on.desc(), stock_receipt.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    if not heads:
        return []
    lines: dict[int, list[ReceiptLineOut]] = {h.id: [] for h in heads}
    for row in conn.execute(
        select(stock_receipt_line, stock_product.c.name.label("product_name"), stock_product.c.unit)
        .select_from(stock_receipt_line.join(stock_product, stock_product.c.id == stock_receipt_line.c.product_id))
        .where(stock_receipt_line.c.receipt_id.in_(list(lines)))
        .order_by(stock_receipt_line.c.id)
    ):
        lines[row.receipt_id].append(ReceiptLineOut.model_validate(row, from_attributes=True))
    return [
        ReceiptOut(
            id=h.id, received_on=h.received_on, supplier_id=h.supplier_id, supplier_name=h.supplier_name,
            reference=h.reference, note=h.note, created_by=h.created_by_name, created_at=h.created_at,
            lines=lines[h.id],
            total_millimes=sum(line.quantity * (line.unit_price_millimes or 0) for line in lines[h.id]),
        )
        for h in heads
    ]


def _receipt(conn: Connection, practice_id: int, receipt_id: int) -> ReceiptOut:
    found = load_receipts(conn, practice_id, stock_receipt.c.id == receipt_id, limit=1)
    if not found:
        raise not_found()
    return found[0]


@router.post("/receipts", status_code=201)
def create_receipt(body: ReceiptIn, user: StockManager, ctx: Ctx, conn: Conn) -> ReceiptOut:
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    received_on = body.received_on or today
    if received_on > today:
        raise unprocessable("La date de réception est dans le futur.", code="day_in_future")
    check_supplier(conn, user.pid, body.supplier_id)
    product_ids = {line.product_id for line in body.lines}
    _products(conn, user.pid, product_ids, active_only=True)
    receipt_id = conn.execute(
        insert(stock_receipt)
        .values(practice_id=user.pid, received_on=received_on, supplier_id=body.supplier_id, reference=body.reference,
                note=body.note, created_by=user.user_id, created_at=now)
        .returning(stock_receipt.c.id)
    ).scalar_one()
    line_ids = conn.execute(
        insert(stock_receipt_line).returning(stock_receipt_line.c.id, sort_by_parameter_order=True),
        [
            {"practice_id": user.pid, "receipt_id": receipt_id, "product_id": line.product_id, "quantity": line.quantity,
             "unit_price_millimes": line.unit_price_millimes, "lot": line.lot, "expires_on": line.expires_on}
            for line in body.lines
        ],
    ).scalars().all()
    conn.execute(
        insert(stock_movement),
        [
            {"practice_id": user.pid, "product_id": line.product_id, "kind": "receipt", "quantity": line.quantity,
             "receipt_line_id": line_id, "unit_cost_millimes": line.unit_price_millimes, "reason": "",
             "created_by": user.user_id, "created_at": now}
            for line, line_id in zip(body.lines, line_ids, strict=True)
        ],
    )
    if body.supplier_id is not None:  # nothing typed twice: the next order goes to the same supplier
        conn.execute(
            update(stock_product)
            .where(stock_product.c.id.in_(product_ids), stock_product.c.practice_id == user.pid,
                   stock_product.c.supplier_id.is_(None))
            .values(supplier_id=body.supplier_id)
        )
    recost(conn, user.pid, sorted(product_ids))
    return _receipt(conn, user.pid, receipt_id)


@router.get("/receipts")
def list_receipts(
    user: StockManagerReader,
    conn: Conn,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReceiptOut]:
    return load_receipts(conn, user.pid, limit=limit, offset=offset)


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: int, user: StockManagerReader, conn: Conn) -> ReceiptOut:
    return _receipt(conn, user.pid, receipt_id)


@router.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, body: ReasonIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> Response:
    receipt = _receipt(conn, user.pid, receipt_id)
    snapshot = {
        "receivedOn": receipt.received_on, "supplier": receipt.supplier_name, "reference": receipt.reference,
        "note": receipt.note, "createdBy": receipt.created_by, "createdAt": receipt.created_at,
        "totalMillimes": receipt.total_millimes,
        "lines": [{"product": line.product_name, "quantity": line.quantity, "unitPriceMillimes": line.unit_price_millimes,
                   "lot": line.lot, "expiresOn": line.expires_on} for line in receipt.lines],
    }
    audit.record(conn, user, entity="stock_receipt", entity_id=receipt_id, action="delete", now=ctx.clock.now(),
                 before=snapshot, reason=body.reason)
    conn.execute(delete(stock_receipt).where(stock_receipt.c.id == receipt_id, stock_receipt.c.practice_id == user.pid))
    recost(conn, user.pid, sorted({line.product_id for line in receipt.lines}))
    return Response(status_code=204)


class LineCorrection(ApiModel):
    quantity: Count | None = None
    unit_price_millimes: Millimes | None = None
    reason: RequiredReason

    @model_validator(mode="after")
    def _quantity_stays(self) -> LineCorrection:
        if "quantity" in self.model_fields_set and self.quantity is None:
            raise ValueError("validation: La quantité ne peut pas être vide.")
        return self


@router.patch("/receipts/{receipt_id}/lines/{line_id}")
def correct_line(receipt_id: int, line_id: int, body: LineCorrection, user: OwnerWriter, ctx: Ctx, conn: Conn) -> ReceiptOut:
    receipt = _receipt(conn, user.pid, receipt_id)
    line = next((x for x in receipt.lines if x.id == line_id), None)
    if line is None:
        raise not_found()
    values = body.model_dump(exclude_unset=True, by_alias=False, include={"quantity", "unit_price_millimes"})
    names = {"quantity": "quantity", "unit_price_millimes": "unitPriceMillimes"}
    before, after = audit.diff(line.model_dump(by_alias=False), values, names)
    if after:
        conn.execute(update(stock_receipt_line).where(stock_receipt_line.c.id == line_id).values(**values))
        if "quantity" in values:
            conn.execute(update(stock_movement).where(stock_movement.c.receipt_line_id == line_id)
                         .values(quantity=values["quantity"]))
        recost(conn, user.pid, [line.product_id])
        audit.record(conn, user, entity="stock_receipt_line", entity_id=line_id, action="update", now=ctx.clock.now(),
                     before={"product": line.product_name, "unit": line.unit, "receivedOn": receipt.received_on,
                             "supplier": receipt.supplier_name, "receiptId": receipt_id, **before},
                     after=after, reason=body.reason.strip())
    return _receipt(conn, user.pid, receipt_id)


# --- movements --------------------------------------------------------------------------------------------------


class MovementOut(ApiModel):
    id: int
    product_id: int
    product_name: str
    unit: Unit
    kind: MovementKind
    quantity: int
    service_id: int | None
    service_name: str | None
    service_name_ar: str | None
    appointment_id: int | None
    patient_name: str | None
    receipt_id: int | None
    receipt_line_id: int | None
    #: The delivery day of a receipt (it may be earlier than ``createdAt``).
    received_on: date | None
    reason: str
    unit_cost_millimes: int | None
    created_by: str | None
    created_at: TunisDateTime


class MovementIn(ApiModel):
    product_id: int
    kind: Literal["use", "waste"]
    quantity: Count
    service_id: int | None = None
    appointment_id: int | None = None
    reason: Reason = ""


class MovementResult(ApiModel):
    movement: MovementOut
    product: ProductOut


def load_movements(conn: Connection, practice_id: int, *conditions: Any, prices: bool, limit: int = 50) -> list[MovementOut]:
    rows = conn.execute(
        select(
            stock_movement,
            stock_product.c.name.label("product_name"),
            stock_product.c.unit,
            service.c.name_fr.label("service_name"),
            service.c.name_ar.label("service_name_ar"),
            patient.c.first_name,
            patient.c.last_name,
            app_user.c.name.label("created_by_name"),
            stock_receipt_line.c.receipt_id,
            stock_receipt.c.received_on,
        )
        .select_from(
            stock_movement.join(stock_product, stock_product.c.id == stock_movement.c.product_id)
            .outerjoin(service, service.c.id == stock_movement.c.service_id)
            .outerjoin(appointment, appointment.c.id == stock_movement.c.appointment_id)
            .outerjoin(patient, patient.c.id == appointment.c.patient_id)
            .outerjoin(app_user, app_user.c.id == stock_movement.c.created_by)
            .outerjoin(stock_receipt_line, stock_receipt_line.c.id == stock_movement.c.receipt_line_id)
            .outerjoin(stock_receipt, stock_receipt.c.id == stock_receipt_line.c.receipt_id)
        )
        .where(stock_movement.c.practice_id == practice_id, *conditions)
        .order_by(stock_movement.c.created_at.desc(), stock_movement.c.id.desc())
        .limit(limit)
    ).all()
    return [
        MovementOut(
            id=r.id, product_id=r.product_id, product_name=r.product_name, unit=r.unit, kind=r.kind, quantity=r.quantity,
            service_id=r.service_id, service_name=r.service_name, service_name_ar=r.service_name_ar or None,
            appointment_id=r.appointment_id,
            patient_name=f"{r.first_name} {r.last_name}" if r.first_name is not None else None,
            receipt_id=r.receipt_id, receipt_line_id=r.receipt_line_id, received_on=r.received_on, reason=r.reason, unit_cost_millimes=r.unit_cost_millimes if prices else None,
            created_by=r.created_by_name, created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/movements", status_code=201)
def create_movement(body: MovementIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> MovementResult:
    if body.kind == "waste" and user.role not in MANAGERS:
        raise forbidden()
    _products(conn, user.pid, {body.product_id}, active_only=True)
    service_id = body.service_id
    if service_id is not None:
        found = conn.execute(select(service.c.id).where(service.c.id == service_id, service.c.practice_id == user.pid)).first()
        if found is None:
            raise unprocessable("Acte introuvable dans le cabinet.", code="invalid_service")
    if body.appointment_id is not None:
        appt = conn.execute(
            select(appointment.c.service_id)
            .where(appointment.c.id == body.appointment_id, appointment.c.practice_id == user.pid)
        ).first()
        if appt is None:
            raise unprocessable("Rendez-vous introuvable dans le cabinet.", code="invalid_appointment")
        if service_id is None:
            service_id = appt.service_id  # the material of an appointment counts for its act
    movement_id = conn.execute(
        insert(stock_movement)
        .values(practice_id=user.pid, product_id=body.product_id, kind=body.kind, quantity=-body.quantity,
                service_id=service_id, appointment_id=body.appointment_id, reason=body.reason, created_by=user.user_id,
                created_at=ctx.clock.now())
        .returning(stock_movement.c.id)
    ).scalar_one()
    recost(conn, user.pid, [body.product_id])
    prices = sees_prices(user)
    (movement,) = load_movements(conn, user.pid, stock_movement.c.id == movement_id, prices=prices, limit=1)
    (product,) = load_products(conn, user.pid, today_tunis(ctx.clock), prices=prices, product_ids=[body.product_id])
    return MovementResult(movement=movement, product=product)


@router.get("/movements")
def list_movements(
    user: StaffUser,
    conn: Conn,
    product_id: Annotated[int | None, Query(alias="productId")] = None,
    appointment_id: Annotated[int | None, Query(alias="appointmentId")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MovementOut]:
    conditions = []
    if product_id is not None:
        conditions.append(stock_movement.c.product_id == product_id)
    if appointment_id is not None:
        conditions.append(stock_movement.c.appointment_id == appointment_id)
    return load_movements(conn, user.pid, *conditions, prices=sees_prices(user), limit=limit)


@router.delete("/movements/{movement_id}", status_code=204)
def delete_movement(movement_id: int, body: ReasonIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> Response:
    found = load_movements(conn, user.pid, stock_movement.c.id == movement_id, prices=True, limit=1)
    if not found:
        raise not_found()
    m = found[0]
    if m.kind == "receipt":
        raise conflict("Ce mouvement vient d'une réception : supprimez la réception.", code="receipt_movement")
    snapshot = {"product": m.product_name, "kind": m.kind, "quantity": m.quantity, "service": m.service_name,
                "appointmentId": m.appointment_id, "reason": m.reason, "unitCostMillimes": m.unit_cost_millimes,
                "createdBy": m.created_by, "createdAt": m.created_at}
    audit.record(conn, user, entity="stock_movement", entity_id=movement_id, action="delete", now=ctx.clock.now(),
                 before=snapshot, reason=body.reason)
    conn.execute(delete(stock_movement).where(stock_movement.c.id == movement_id))
    recost(conn, user.pid, [m.product_id])
    return Response(status_code=204)


# --- inventory --------------------------------------------------------------------------------------------------


class CountIn(ApiModel):
    product_id: int
    counted: Annotated[int, Field(ge=0, le=MAX_QUANTITY, strict=True)]


class InventoryIn(ApiModel):
    reason: RequiredReason
    counts: Annotated[list[CountIn], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def _each_product_once(self) -> InventoryIn:
        if len({c.product_id for c in self.counts}) != len(self.counts):
            raise ValueError("validation: Chaque produit une seule fois.")
        return self


class InventoryOut(ApiModel):
    adjusted: int
    products: list[ProductOut]


@router.post("/inventory")
def inventory(body: InventoryIn, user: StockManager, ctx: Ctx, conn: Conn) -> InventoryOut:
    ids = [c.product_id for c in body.counts]
    _products(conn, user.pid, set(ids), active_only=False)
    levels = stock_levels(conn, user.pid, ids)
    now = ctx.clock.now()
    rows = [
        {"practice_id": user.pid, "product_id": c.product_id, "kind": "adjust", "quantity": c.counted - levels.get(c.product_id, 0),
         "reason": body.reason, "created_by": user.user_id, "created_at": now}
        for c in body.counts
        if c.counted != levels.get(c.product_id, 0)
    ]
    if rows:
        conn.execute(insert(stock_movement), rows)
        recost(conn, user.pid, sorted({row["product_id"] for row in rows}))
    products = load_products(conn, user.pid, today_tunis(ctx.clock), prices=sees_prices(user), product_ids=ids)
    return InventoryOut(adjusted=len(rows), products=products)
