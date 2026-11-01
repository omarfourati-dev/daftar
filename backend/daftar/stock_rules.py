"""Rules of the stock module that need no database (spec stock-hygiène, section 4).

- **Traffic light** (:func:`stock_status`): ``unreceived`` (grey "pas encore reçu") while nothing was ever delivered
  or counted, ``empty`` at 0 or below, ``low`` when the stock has reached the minimum quantity (the alarm threshold the
  practice set), else ``ok``. A product without a minimum is never ``low``.
- **Material cost** (:func:`moving_costs`, spec 4.1 "gleitender Durchschnittspreis", review H2/M1): the moving average
  of what is in stock. A delivery mixes with the stock left – ``(max(stock, 0) × average + quantity × price) /
  (max(stock, 0) + quantity)``, half up to the millime; a use, a loss or an inventory count leaves at the average of
  that moment. Lines without a price keep the average; what was used before any price was known takes the first one.
  The movements are taken in the order they happened (:func:`cost_order`): a delivery entered days later counts from
  the end of its delivery day. The costs are kept with the movements and computed again from the start whenever a
  movement or a receipt line changes, so a corrected price corrects every cost that depended on it.
- **Expiry** (:func:`soonest_expiry`): a practice uses the lots that expire first (FEFO), so what is left lies in the
  lots that expire last; lots without a date count as never expiring. ``expired`` before today, ``soon`` within the
  next :data:`EXPIRY_SOON_DAYS` days.
- **What to order** (:func:`needs_order`, :func:`reorder_quantity`): active products with a minimum whose stock has
  reached it; the proposal brings the stock back to twice the minimum (a negative stock counts as 0).
- **Start lists** (:func:`starter_items`, section 4.4): typical products per specialty, FR and AR names – only ever
  created when the practice asks for them. What is used per patient (carpules, needles, syringes, tubes) is counted
  by the piece, so "used for this act" stays exact; what is opened now and then (gloves, masks) by the box.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal

from .clock import TUNIS

Category = Literal[
    "hygiene", "anesthesie", "restauration", "endodontie", "prothese", "chirurgie", "prelevements", "injection",
    "pansements", "bureau", "autre",
]
CATEGORIES: tuple[Category, ...] = (
    "hygiene", "anesthesie", "restauration", "endodontie", "prothese", "chirurgie", "prelevements", "injection",
    "pansements", "bureau", "autre",
)
Unit = Literal["piece", "boite", "flacon", "carpule", "paquet", "sachet", "tube", "rouleau", "paire", "ml", "g"]
UNITS: tuple[Unit, ...] = ("piece", "boite", "flacon", "carpule", "paquet", "sachet", "tube", "rouleau", "paire", "ml", "g")
StockStatus = Literal["ok", "low", "empty", "unreceived"]
ExpiryState = Literal["expired", "soon"]

EXPIRY_SOON_DAYS = 30
MAX_QUANTITY = 100_000


def stock_status(quantity: int, min_quantity: int, *, received: bool = True) -> StockStatus:
    if not received:
        return "unreceived"
    if quantity <= 0:
        return "empty"
    if min_quantity > 0 and quantity <= min_quantity:
        return "low"
    return "ok"


def _half_up(numerator: int, denominator: int) -> int:
    return (2 * numerator + denominator) // (2 * denominator)  # integers only


@dataclass(frozen=True)
class CostMove:
    """One movement of a product for :func:`moving_costs`: id, kind, signed quantity, unit price (receipts only)."""

    id: int
    kind: str
    quantity: int
    price: int | None = None


@dataclass
class Costs:
    #: Movement id → unit cost in millimes (a receipt: its line's price; others: the average of that moment).
    unit_costs: dict[int, int | None] = field(default_factory=dict)
    #: The average after the last movement – the product's price today (None without any price).
    average: int | None = None


def moving_costs(moves: Iterable[CostMove]) -> Costs:
    """The moving average through ``moves`` (in the order of :func:`cost_order`)."""
    costs = Costs()
    stock = 0
    waiting: list[int] = []  # left the stock before any price was known
    for move in moves:
        if move.kind == "receipt":
            costs.unit_costs[move.id] = move.price
            if move.price is not None:
                base = max(stock, 0)
                first = costs.average is None
                costs.average = move.price if first else _half_up(base * costs.average + move.quantity * move.price,
                                                                  base + move.quantity)
                if first:
                    costs.unit_costs.update(dict.fromkeys(waiting, costs.average))
                    waiting.clear()
        else:
            costs.unit_costs[move.id] = costs.average
            if costs.average is None:
                waiting.append(move.id)
        stock += move.quantity
    return costs


def cost_order(move_id: int, kind: str, created_at: datetime, received_on: date | None) -> tuple[datetime, int]:
    """Sort key of a movement for the costs: when it happened (then in the order it was recorded). A receipt entered
    after its delivery day counts from the end of that day – the material was on the shelf."""
    at = created_at
    if kind == "receipt" and received_on is not None and received_on < created_at.astimezone(TUNIS).date():
        at = datetime.combine(received_on + timedelta(days=1), time(0), tzinfo=TUNIS)
    return (at, move_id)


def soonest_expiry(stock: int, lots: Iterable[tuple[date | None, int]]) -> date | None:
    """The earliest expiry date among the lots still in stock (``[(expires_on or None, quantity received), …]``)."""
    if stock <= 0:
        return None
    lots = list(lots)
    remaining = stock - sum(q for expires, q in lots if expires is None)
    soonest: date | None = None
    for expires, quantity in sorted(((e, q) for e, q in lots if e is not None), key=lambda lot: lot[0], reverse=True):
        if remaining <= 0:
            break
        soonest = expires
        remaining -= quantity
    return soonest


def expiry_state(expires_on: date | None, today: date) -> ExpiryState | None:
    if expires_on is None:
        return None
    if expires_on < today:
        return "expired"
    if expires_on < today + timedelta(days=EXPIRY_SOON_DAYS):
        return "soon"
    return None


def needs_order(*, stock: int, min_quantity: int, active: bool, received: bool = True) -> bool:
    """Active, with a threshold, at or below it – and delivered or counted once (a start list is not an order)."""
    return active and received and min_quantity > 0 and stock <= min_quantity


def reorder_quantity(*, stock: int, min_quantity: int) -> int:
    return max(2 * min_quantity - max(stock, 0), 1)


# --- start lists (section 4.4) -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StarterItem:
    name_fr: str
    name_ar: str
    category: Category
    unit: Unit
    min_quantity: int


def _s(name_fr: str, name_ar: str, category: Category, unit: Unit, minimum: int) -> StarterItem:
    return StarterItem(name_fr, name_ar, category, unit, minimum)


GLOVES = _s("Gants d’examen", "قفازات الفحص", "hygiene", "boite", 4)
MASKS = _s("Masques chirurgicaux", "كمامات طبية", "hygiene", "boite", 2)
GEL = _s("Gel hydroalcoolique", "جل كحولي معقّم", "hygiene", "flacon", 2)
SURFACES = _s("Désinfectant de surfaces", "مطهّر الأسطح", "hygiene", "flacon", 2)
SHEETS = _s("Draps d’examen", "أغطية سرير الفحص", "hygiene", "rouleau", 2)
COMPRESSES = _s("Compresses stériles", "كمادات معقّمة", "pansements", "paquet", 5)
PAPER = _s("Ordonnanciers", "دفاتر الوصفات", "bureau", "piece", 2)

_DENTIST = (
    GLOVES,
    MASKS,
    _s("Carpules d’articaïne", "خراطيش أرتيكايين", "anesthesie", "carpule", 50),
    _s("Aiguilles dentaires", "إبر الأسنان", "anesthesie", "piece", 50),
    _s("Composite", "حشوة كومبوزيت", "restauration", "piece", 3),
    _s("Acide de mordançage", "حمض التخريش", "restauration", "piece", 1),
    _s("Rouleaux de coton", "لفائف القطن", "hygiene", "paquet", 2),
    _s("Pompes à salive", "شفاطات اللعاب", "hygiene", "paquet", 2),
    _s("Gobelets", "أكواب", "hygiene", "paquet", 2),
    _s("Sachets de stérilisation", "أكياس التعقيم", "hygiene", "boite", 2),
    _s("Limes endodontiques", "مبارد علاج العصب", "endodontie", "boite", 1),
    SURFACES,
)
_GENERALIST = (
    GLOVES,
    _s("Seringues 5 ml", "حقن 5 مل", "injection", "piece", 50),
    _s("Aiguilles", "إبر", "injection", "piece", 50),
    _s("Tubes EDTA", "أنابيب EDTA", "prelevements", "piece", 20),
    _s("Tubes secs", "أنابيب جافة", "prelevements", "piece", 20),
    _s("Tubes citrate", "أنابيب سيترات", "prelevements", "piece", 20),
    COMPRESSES,
    _s("Bandelettes urinaires", "شرائط تحليل البول", "prelevements", "boite", 1),
    _s("Bandelettes glycémie", "شرائط قياس السكر", "prelevements", "boite", 1),
    _s("Abaisse-langues", "خافضات اللسان", "hygiene", "boite", 1),
    GEL,
    SHEETS,
    SURFACES,
)
_PEDIATRIC = (
    GLOVES,
    _s("Abaisse-langues", "خافضات اللسان", "hygiene", "boite", 1),
    _s("Embouts d’otoscope", "رؤوس منظار الأذن", "hygiene", "boite", 1),
    _s("Seringues 1 ml", "حقن 1 مل", "injection", "piece", 30),
    _s("Pansements enfants", "ضمادات للأطفال", "pansements", "boite", 1),
    COMPRESSES,
    GEL,
    SHEETS,
    SURFACES,
)
_PHYSIO = (
    _s("Huile de massage", "زيت التدليك", "autre", "flacon", 2),
    _s("Gel conducteur", "جل موصّل", "autre", "flacon", 2),
    _s("Bandes de contention", "أربطة ضاغطة", "pansements", "piece", 4),
    _s("Électrodes adhésives", "أقطاب لاصقة", "autre", "paquet", 2),
    SHEETS,
    GEL,
    SURFACES,
)
_GENERIC = (GLOVES, MASKS, GEL, SURFACES, SHEETS, COMPRESSES, PAPER)

STARTERS: dict[str, tuple[StarterItem, ...]] = {
    "dentiste": _DENTIST,
    "generaliste": _GENERALIST,
    "pediatre": _PEDIATRIC,
    "kinesitherapeute": _PHYSIO,
}


def starter_items(specialty: str) -> tuple[StarterItem, ...]:
    return STARTERS.get(specialty, _GENERIC)
