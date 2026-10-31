"""The owner's view of the material (spec stock-hygiène 4.3): spending and use per act, CSV of the month.

- ``GET /api/stock/stats?month=YYYY-MM`` (owner) → ``{month, spendingMillimes, previousSpendingMillimes, unpricedLines,
  bySupplier:[{name, amountMillimes}], byCategory:[{category, amountMillimes}], usageMillimes, wasteMillimes,
  byService:[{serviceId, name, treatments, materialCostMillimes, perTreatmentMillimes, items:[…]}],
  topMaterials:[{productId, name, unit, quantity, costMillimes}]}``.
  Spending = Σ quantity × unit price of the receipts dated in the month (lines without a price count 0 and are counted
  in ``unpricedLines``). Material cost of a use = quantity × the average purchase price kept with it (for a use
  recorded before any price was known: today's average). ``treatments`` = appointments of that act done in the month;
  ``perTreatmentMillimes`` = material cost / treatments (null without treatments). Uses without act come last
  (``serviceId`` null).
- ``GET /api/stock/export.csv?month=`` (owner) → every movement of the month (receipts by their delivery date),
  ``;``-separated UTF-8 with BOM like the import report, amounts in dinars with three decimals; no patient names.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import Connection, func, select

from .clock import TUNIS, now_tunis
from .deps import Conn, Ctx, OwnerUser
from .imports import defuse
from .schemas import ApiModel
from .stock import average_costs
from .stock_rules import Category, Unit
from .tables import app_user, appointment, service, stock_movement, stock_product, stock_receipt, stock_receipt_line, supplier

router = APIRouter(prefix="/api/stock", tags=["stock"])

Month = Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
TOP_MATERIALS = 5
CATEGORY_FR = {
    "hygiene": "Hygiène", "anesthesie": "Anesthésie", "restauration": "Restauration", "endodontie": "Endodontie",
    "prothese": "Prothèse", "chirurgie": "Chirurgie", "prelevements": "Prélèvements", "injection": "Injections",
    "pansements": "Pansements", "bureau": "Bureau", "autre": "Autre",
}
KIND_FR = {"receipt": "Réception", "use": "Utilisation", "adjust": "Inventaire", "waste": "Perte"}
UNIT_FR = {"piece": "pièce", "boite": "boîte", "flacon": "flacon", "carpule": "carpule", "paquet": "paquet",
           "sachet": "sachet", "tube": "tube", "rouleau": "rouleau", "paire": "paire", "ml": "ml", "g": "g"}


class Amount(ApiModel):
    name: str | None
    amount_millimes: int


class CategoryAmount(ApiModel):
    category: Category
    amount_millimes: int


class UsageItem(ApiModel):
    product_id: int
    name: str
    unit: Unit
    quantity: int
    cost_millimes: int


class ServiceUsage(ApiModel):
    service_id: int | None
    name: str | None
    treatments: int
    material_cost_millimes: int
    per_treatment_millimes: int | None
    items: list[UsageItem]


class StockStatsOut(ApiModel):
    month: str
    spending_millimes: int
    previous_spending_millimes: int
    unpriced_lines: int
    by_supplier: list[Amount]
    by_category: list[CategoryAmount]
    usage_millimes: int
    waste_millimes: int
    by_service: list[ServiceUsage]
    top_materials: list[UsageItem]


def _month(ctx: Any, month: str | None) -> tuple[int, int]:
    if month is None:
        local = now_tunis(ctx.clock)
        return local.year, local.month
    return int(month[:4]), int(month[5:])


def _days(year: int, month: int) -> tuple[date, date]:
    """[first day, first day of the next month)."""
    nxt = (year + 1, 1) if month == 12 else (year, month + 1)
    return date(year, month, 1), date(*nxt, 1)


def _instants(year: int, month: int) -> tuple[datetime, datetime]:
    first, nxt = _days(year, month)
    return datetime(first.year, first.month, 1, tzinfo=TUNIS), datetime(nxt.year, nxt.month, 1, tzinfo=TUNIS)


def _receipt_lines(conn: Connection, practice_id: int, first: date, nxt: date) -> list[Any]:
    return conn.execute(
        select(
            stock_receipt_line.c.id, stock_receipt_line.c.quantity, stock_receipt_line.c.unit_price_millimes,
            stock_receipt_line.c.lot, stock_receipt.c.received_on, stock_receipt.c.reference,
            stock_product.c.name.label("product_name"), stock_product.c.category, stock_product.c.unit,
            supplier.c.name.label("supplier_name"), app_user.c.name.label("created_by_name"),
        )
        .select_from(
            stock_receipt_line.join(stock_receipt, stock_receipt.c.id == stock_receipt_line.c.receipt_id)
            .join(stock_product, stock_product.c.id == stock_receipt_line.c.product_id)
            .outerjoin(supplier, supplier.c.id == stock_receipt.c.supplier_id)
            .outerjoin(app_user, app_user.c.id == stock_receipt.c.created_by)
        )
        .where(stock_receipt_line.c.practice_id == practice_id, stock_receipt.c.received_on >= first,
               stock_receipt.c.received_on < nxt)
        .order_by(stock_receipt.c.received_on, stock_receipt_line.c.id)
    ).all()


def _movements(conn: Connection, practice_id: int, start: datetime, end: datetime, kinds: tuple[str, ...]) -> list[Any]:
    return conn.execute(
        select(
            stock_movement.c.id, stock_movement.c.product_id, stock_movement.c.kind, stock_movement.c.quantity,
            stock_movement.c.unit_cost_millimes, stock_movement.c.service_id, stock_movement.c.reason,
            stock_movement.c.created_at, stock_product.c.name.label("product_name"), stock_product.c.category,
            stock_product.c.unit, service.c.name_fr.label("service_name"), app_user.c.name.label("created_by_name"),
        )
        .select_from(
            stock_movement.join(stock_product, stock_product.c.id == stock_movement.c.product_id)
            .outerjoin(service, service.c.id == stock_movement.c.service_id)
            .outerjoin(app_user, app_user.c.id == stock_movement.c.created_by)
        )
        .where(stock_movement.c.practice_id == practice_id, stock_movement.c.kind.in_(kinds),
               stock_movement.c.created_at >= start, stock_movement.c.created_at < end)
        .order_by(stock_movement.c.created_at, stock_movement.c.id)
    ).all()


def _costs(conn: Connection, practice_id: int, rows: list[Any]) -> dict[int, int]:
    """Movement id → material cost in millimes (positive for what left the stock)."""
    missing = sorted({r.product_id for r in rows if r.unit_cost_millimes is None})
    today_average = average_costs(conn, practice_id, missing) if missing else {}
    return {
        r.id: -r.quantity * (r.unit_cost_millimes if r.unit_cost_millimes is not None else today_average.get(r.product_id) or 0)
        for r in rows
    }


@dataclass
class _Usage:
    name: str | None
    cost: int = 0
    items: dict[int, UsageItem] = field(default_factory=dict)

    def add(self, row: Any, cost: int) -> None:
        self.cost += cost
        item = self.items.get(row.product_id)
        if item is None:
            self.items[row.product_id] = UsageItem(product_id=row.product_id, name=row.product_name, unit=row.unit,
                                                   quantity=-row.quantity, cost_millimes=cost)
        else:
            item.quantity -= row.quantity
            item.cost_millimes += cost


def _by_cost(items: Any) -> list[UsageItem]:
    return sorted(items, key=lambda i: (-i.cost_millimes, i.name.lower()))


def _per(cost: int, treatments: int) -> int | None:
    """Material cost per treatment, rounded half up to the millime (None without treatments)."""
    return (2 * cost + treatments) // (2 * treatments) if treatments else None


def _spending(lines: list[Any]) -> int:
    return sum(line.quantity * (line.unit_price_millimes or 0) for line in lines)


@router.get("/stats")
def stats(user: OwnerUser, ctx: Ctx, conn: Conn, month: Month = None) -> StockStatsOut:
    year, mon = _month(ctx, month)
    first, nxt = _days(year, mon)
    lines = _receipt_lines(conn, user.pid, first, nxt)
    previous = _receipt_lines(conn, user.pid, *_days(*((year - 1, 12) if mon == 1 else (year, mon - 1))))
    suppliers: dict[str | None, int] = defaultdict(int)
    categories: dict[str, int] = defaultdict(int)
    for line in lines:
        amount = line.quantity * (line.unit_price_millimes or 0)
        suppliers[line.supplier_name] += amount
        categories[line.category] += amount

    start, end = _instants(year, mon)
    moved = _movements(conn, user.pid, start, end, ("use", "waste"))
    costs = _costs(conn, user.pid, moved)
    uses = [m for m in moved if m.kind == "use"]
    per_service: dict[int | None, _Usage] = {}
    materials = _Usage(name=None)
    for m in uses:
        per_service.setdefault(m.service_id, _Usage(name=m.service_name)).add(m, costs[m.id])
        materials.add(m, costs[m.id])
    treated = [sid for sid in per_service if sid is not None]
    treatments = dict(
        conn.execute(
            select(appointment.c.service_id, func.count())
            .where(appointment.c.practice_id == user.pid, appointment.c.service_id.in_(treated),
                   appointment.c.status == "done", appointment.c.starts_at >= start, appointment.c.starts_at < end)
            .group_by(appointment.c.service_id)
        ).all()
    ) if treated else {}
    by_service = sorted(
        (
            ServiceUsage(
                service_id=sid, name=usage.name, treatments=treatments.get(sid, 0), material_cost_millimes=usage.cost,
                per_treatment_millimes=_per(usage.cost, treatments.get(sid, 0)),
                items=_by_cost(usage.items.values()),
            )
            for sid, usage in per_service.items()
        ),
        key=lambda s: (s.service_id is None, -s.material_cost_millimes, (s.name or "").lower()),
    )
    return StockStatsOut(
        month=f"{year:04d}-{mon:02d}",
        spending_millimes=_spending(lines),
        previous_spending_millimes=_spending(previous),
        unpriced_lines=sum(1 for line in lines if line.unit_price_millimes is None),
        by_supplier=[Amount(name=name, amount_millimes=amount)
                     for name, amount in sorted(suppliers.items(), key=lambda kv: (-kv[1], kv[0] is None, kv[0] or ""))],
        by_category=[CategoryAmount(category=c, amount_millimes=amount)  # type: ignore[arg-type]
                     for c, amount in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))],
        usage_millimes=sum(costs[m.id] for m in uses),
        waste_millimes=sum(costs[m.id] for m in moved if m.kind == "waste"),
        by_service=by_service,
        top_materials=_by_cost(materials.items.values())[:TOP_MATERIALS],
    )


def _dinars(millimes: int | None) -> str:
    if millimes is None:
        return ""
    sign = "-" if millimes < 0 else ""
    whole, rest = divmod(abs(millimes), 1000)
    return f"{sign}{whole},{rest:03d}"


@router.get("/export.csv")
def export_csv(user: OwnerUser, ctx: Ctx, conn: Conn, month: Month = None) -> Response:
    year, mon = _month(ctx, month)
    rows: list[tuple[tuple[date, int, int], list[str]]] = []
    for line in _receipt_lines(conn, user.pid, *_days(year, mon)):
        amount = line.quantity * line.unit_price_millimes if line.unit_price_millimes is not None else None
        rows.append(((line.received_on, 0, line.id), [
            line.received_on.strftime("%d/%m/%Y"), KIND_FR["receipt"], defuse(line.product_name), CATEGORY_FR[line.category],
            str(line.quantity), UNIT_FR[line.unit], _dinars(line.unit_price_millimes), _dinars(amount),
            defuse(line.supplier_name or ""), defuse(line.reference), "", defuse(line.lot), defuse(line.created_by_name or ""),
        ]))
    moved = _movements(conn, user.pid, *_instants(year, mon), ("use", "adjust", "waste"))
    costs = _costs(conn, user.pid, moved)
    for m in moved:
        day = m.created_at.astimezone(TUNIS).date()
        unit_cost = m.unit_cost_millimes
        rows.append(((day, 1, m.id), [
            day.strftime("%d/%m/%Y"), KIND_FR[m.kind], defuse(m.product_name), CATEGORY_FR[m.category], str(m.quantity),
            UNIT_FR[m.unit], _dinars(unit_cost), _dinars(-costs[m.id] if costs[m.id] else None), "", "",
            defuse(m.service_name or ""), defuse(m.reason), defuse(m.created_by_name or ""),
        ]))
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Date", "Type", "Produit", "Catégorie", "Quantité", "Unité", "Prix unitaire (DT)", "Montant (DT)",
                     "Fournisseur", "Réf. réception", "Acte", "Motif / lot", "Par"])
    for _, cells in sorted(rows, key=lambda r: r[0]):  # free text is defused above, our numbers may start with "-"
        writer.writerow(cells)
    name = f"stock-{year:04d}-{mon:02d}.csv"
    return Response(
        ("﻿" + out.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
