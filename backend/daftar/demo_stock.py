"""The stock of a demo practice (spec stock-hygiène 8): two suppliers, the start list of the specialty with invented
prices, four deliveries (one last month to compare with, one today), the material used for the acts done in the last
two weeks, boxes opened at the desk, one loss – so that "À commander", "Bientôt périmé" and the owner's figures show
something from the first click.

The numbers add up like in a real practice: every delivery comes before what it is used for, no stock goes below
zero, two products end at or under their minimum ("à commander") and one has a lot that expires within 30 days.
Supplier numbers use the non-existent prefix 00 like the demo patients.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Connection, insert

from .clock import TUNIS, at_tunis
from .stock import recost
from .stock_rules import StarterItem, starter_items
from .tables import stock_movement, stock_product, stock_receipt, stock_receipt_line, supplier

#: Invented unit prices (millimes) of the start-list products; others get one by their unit.
PRICES = {
    "Gants d’examen": 13_500, "Masques chirurgicaux": 7_500, "Carpules d’articaïne": 950, "Aiguilles dentaires": 350,
    "Composite": 38_000, "Acide de mordançage": 9_500, "Rouleaux de coton": 4_800, "Pompes à salive": 6_500,
    "Gobelets": 3_900, "Sachets de stérilisation": 24_000, "Limes endodontiques": 32_000,
    "Désinfectant de surfaces": 16_500, "Seringues 5 ml": 180, "Aiguilles": 90, "Tubes EDTA": 450, "Tubes secs": 400,
    "Tubes citrate": 520, "Compresses stériles": 3_200, "Bandelettes urinaires": 21_000, "Bandelettes glycémie": 29_000,
    "Abaisse-langues": 5_500, "Gel hydroalcoolique": 8_900, "Draps d’examen": 11_500, "Seringues 1 ml": 160,
}
PRICE_BY_UNIT = {"piece": 600, "carpule": 950, "boite": 15_000, "flacon": 12_000, "paquet": 6_000, "sachet": 2_500,
                 "tube": 8_000, "rouleau": 9_000, "paire": 1_200, "ml": 100, "g": 100}
#: What one act uses (service name → [(product, quantity, probability)]).
USES: dict[str, list[tuple[str, int, float]]] = {
    "Soin carie / composite": [("Carpules d’articaïne", 1, 1.0), ("Aiguilles dentaires", 1, 1.0), ("Composite", 1, 0.3)],
    "Extraction": [("Carpules d’articaïne", 2, 1.0), ("Aiguilles dentaires", 1, 1.0)],
    "Traitement de canal": [("Carpules d’articaïne", 1, 1.0), ("Aiguilles dentaires", 1, 1.0)],
    "Urgence / douleur": [("Carpules d’articaïne", 1, 0.8), ("Aiguilles dentaires", 1, 0.8)],
    "Vaccination": [("Seringues 5 ml", 1, 1.0), ("Seringues 1 ml", 1, 1.0), ("Aiguilles", 1, 1.0)],
    "Consultation": [("Tubes EDTA", 1, 0.25), ("Tubes secs", 1, 0.25), ("Aiguilles", 1, 0.25)],
    "Urgence": [("Compresses stériles", 1, 0.6), ("Seringues 5 ml", 1, 0.4), ("Aiguilles", 1, 0.4)],
}
OPENED_AT_THE_DESK = ("boite", "flacon", "paquet", "rouleau")
#: Indices in the start list: two end "à commander", one has a lot that expires soon.
LOW = (1, 4)
B_DELIVERY, TODAY_DELIVERY, LAST_MONTH = (0, 2, 5), (1, 3), (0, 1, 2)


@dataclass
class _Product:
    id: int
    item: StarterItem
    index: int
    price: int


def _price(item: StarterItem) -> int:
    return PRICES.get(item.name_fr, PRICE_BY_UNIT[item.unit])


def _last_month_delivery(today: date) -> date:
    """A day of last month, before the first delivery of this period (today − 20 days)."""
    tenth_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=10)
    return min(tenth_of_last_month, today - timedelta(days=25))


def seed_stock(
    conn: Connection,
    *,
    practice_id: int,
    user_id: int,
    specialty: str,
    arabic: bool,
    now: datetime,
    plans: Sequence[Any],
    rng: random.Random,
) -> None:
    """``plans``: the demo appointments (``status``, ``svc.name_fr``, ``svc.id``, ``id``, ``start``, ``end``)."""
    today = now.astimezone(TUNIS).date()
    first_name = "Dentalia Sfax" if specialty == "dentiste" else "Pharma Distribution Tunis"
    suppliers = [
        conn.execute(insert(supplier).values(practice_id=practice_id, name=name, phone=phone, whatsapp=whatsapp,
                                             note=note, created_at=now).returning(supplier.c.id)).scalar_one()
        for name, phone, whatsapp, note in (
            (first_name, "+21600000091", "+21600000091", "Livraison le mardi" if not arabic else "التوصيل يوم الثلاثاء"),
            ("Médical Sud", "+21600000092", None, ""),
        )
    ]
    items = starter_items(specialty)
    ids = conn.execute(
        insert(stock_product).returning(stock_product.c.id, sort_by_parameter_order=True),
        [{"practice_id": practice_id, "name": item.name_ar if arabic else item.name_fr, "category": item.category,
          "unit": item.unit, "min_quantity": item.min_quantity, "supplier_id": suppliers[n % 2], "created_at": now}
         for n, item in enumerate(items)],
    ).scalars().all()
    products = [_Product(pid, item, n, _price(item)) for n, (pid, item) in enumerate(zip(ids, items, strict=True))]
    by_name = {p.item.name_fr: p for p in products}

    # what left the stock: material of the acts done, boxes opened at the desk, one loss
    outflows: list[dict[str, Any]] = []
    for plan in sorted((p for p in plans if p.status == "done" and p.end <= now), key=lambda p: p.end):
        for name, quantity, probability in USES.get(plan.svc.name_fr, []):
            if name in by_name and rng.random() < probability:
                outflows.append({"product": by_name[name], "kind": "use", "quantity": quantity, "at": plan.end,
                                 "service_id": plan.svc.id, "appointment_id": plan.id})
    desk = [p for p in products if p.item.unit in OPENED_AT_THE_DESK and p.item.category == "hygiene"] or products[:2]
    for offset in range(-13, 0, 3):
        day = today + timedelta(days=offset)
        outflows.append({"product": desk[(offset // 3) % len(desk)], "kind": "use", "quantity": 1,
                         "at": at_tunis(day, time(8, 15)), "service_id": None, "appointment_id": None})
    outflows.append({"product": products[0], "kind": "waste", "quantity": 1, "at": at_tunis(today - timedelta(days=3), time(17, 0)),
                     "service_id": None, "appointment_id": None,
                     "reason": "Emballage abîmé" if not arabic else "علبة تالفة"})
    used: dict[int, int] = defaultdict(int)
    for out in outflows:
        used[out["product"].index] += out["quantity"]

    # deliveries: everything used comes in before it is used; what is left is the stock of today
    lines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in products:
        minimum = p.item.min_quantity
        target = max(1, minimum // 2) if p.index == LOW[0] else minimum if p.index == LOW[1] else 2 * minimum + rng.randint(1, max(1, minimum))
        total = used[p.index] + target
        last_month = (total * 3) // 10 if p.index in LAST_MONTH else 0
        later = target // 3 if p.index in B_DELIVERY else 0
        today_part = max(1, target // 4) if p.index in TODAY_DELIVERY and target >= 2 else 0
        first = total - last_month - later - today_part
        if first < 1:
            later = today_part = 0
            first = total - last_month
        soon = p.index == len(products) - 1  # one lot that expires within 30 days
        lot = f"L{today.year % 100}{p.index:02d}{rng.randint(10, 99)}"
        expires = today + timedelta(days=18) if soon else (today + timedelta(days=rng.randint(200, 700))
                                                            if p.item.category in ("anesthesie", "injection", "prelevements") else None)
        for key, quantity, price in (("last_month", last_month, p.price), ("first", first, p.price),
                                     ("later", later, round(p.price * 1.06 / 10) * 10), ("today", today_part, p.price)):
            if quantity > 0:
                lines[key].append({"product": p, "quantity": quantity, "price": price,
                                   "lot": lot if expires else "", "expires_on": expires})
    deliveries = (
        ("last_month", _last_month_delivery(today), suppliers[0], "BL 1180"),
        ("first", today - timedelta(days=20), suppliers[0], "BL 1204"),
        ("later", today - timedelta(days=6), suppliers[1], f"F-{today.year}-311"),
        ("today", today, suppliers[0], "BL 1231"),
    )
    for key, day, supplier_id, reference in deliveries:
        if not lines[key]:
            continue
        at = min(now - timedelta(minutes=5), at_tunis(day, time(8, 30)))
        receipt_id = conn.execute(
            insert(stock_receipt).values(practice_id=practice_id, received_on=day, supplier_id=supplier_id,
                                         reference=reference, created_by=user_id, created_at=at)
            .returning(stock_receipt.c.id)
        ).scalar_one()
        line_ids = conn.execute(
            insert(stock_receipt_line).returning(stock_receipt_line.c.id, sort_by_parameter_order=True),
            [{"practice_id": practice_id, "receipt_id": receipt_id, "product_id": line["product"].id,
              "quantity": line["quantity"], "unit_price_millimes": line["price"], "lot": line["lot"],
              "expires_on": line["expires_on"]} for line in lines[key]],
        ).scalars().all()
        conn.execute(insert(stock_movement), [
            {"practice_id": practice_id, "product_id": line["product"].id, "kind": "receipt",
             "quantity": line["quantity"], "receipt_line_id": line_id, "unit_cost_millimes": line["price"],
             "reason": "", "created_by": user_id, "created_at": at}
            for line, line_id in zip(lines[key], line_ids, strict=True)
        ])
    conn.execute(insert(stock_movement), [
        {"practice_id": practice_id, "product_id": out["product"].id, "kind": out["kind"], "quantity": -out["quantity"],
         "service_id": out["service_id"], "appointment_id": out["appointment_id"],
         "reason": out.get("reason", ""), "created_by": user_id, "created_at": min(out["at"], now)}
        for out in outflows
    ])
    recost(conn, practice_id, [p.id for p in products])  # the moving average, as for every real movement
