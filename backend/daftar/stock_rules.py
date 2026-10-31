"""Rules of the stock module that need no database (spec stock-hygiène, section 4).

- **Traffic light** (:func:`stock_status`): ``empty`` at 0 or below, ``low`` when the stock has reached the minimum
  quantity (the alarm threshold the practice set), else ``ok``. A product without a minimum is never ``low``.
- **Average price** (:func:`average_cost`): the purchase prices of the receipts weighted by quantity (lines without a
  price do not count), rounded half up to the millime. A use keeps the average of the moment it was recorded
  (``stock_movement.unit_cost_millimes``) – the material cost of a past treatment never changes afterwards.
- **Expiry** (:func:`soonest_expiry`): a practice uses the lots that expire first (FEFO), so what is left lies in the
  lots that expire last; lots without a date count as never expiring. ``expired`` before today, ``soon`` within the
  next :data:`EXPIRY_SOON_DAYS` days.
- **What to order** (:func:`needs_order`, :func:`reorder_quantity`): active products with a minimum whose stock has
  reached it; the proposal brings the stock back to twice the minimum (a negative stock counts as 0).
- **Start lists** (:func:`starter_items`, section 4.4): typical products per specialty, FR and AR names – only ever
  created when the practice asks for them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

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
StockStatus = Literal["ok", "low", "empty"]
ExpiryState = Literal["expired", "soon"]

EXPIRY_SOON_DAYS = 30
MAX_QUANTITY = 100_000


def stock_status(quantity: int, min_quantity: int) -> StockStatus:
    if quantity <= 0:
        return "empty"
    if min_quantity > 0 and quantity <= min_quantity:
        return "low"
    return "ok"


def average_cost(lines: Iterable[tuple[int, int | None]]) -> int | None:
    """``[(quantity, unit price in millimes or None), …]`` → weighted average in millimes, None without any price."""
    total_quantity = total_price = 0
    for quantity, price in lines:
        if price is None or quantity <= 0:
            continue
        total_quantity += quantity
        total_price += quantity * price
    if total_quantity == 0:
        return None
    return (2 * total_price + total_quantity) // (2 * total_quantity)  # half up, integers only


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


def needs_order(*, stock: int, min_quantity: int, active: bool) -> bool:
    return active and min_quantity > 0 and stock <= min_quantity


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
    _s("Carpules d’articaïne", "خراطيش أرتيكايين", "anesthesie", "boite", 2),
    _s("Aiguilles dentaires", "إبر الأسنان", "anesthesie", "boite", 2),
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
    _s("Seringues 5 ml", "حقن 5 مل", "injection", "boite", 2),
    _s("Aiguilles", "إبر", "injection", "boite", 2),
    _s("Tubes EDTA", "أنابيب EDTA", "prelevements", "boite", 1),
    _s("Tubes secs", "أنابيب جافة", "prelevements", "boite", 1),
    _s("Tubes citrate", "أنابيب سيترات", "prelevements", "boite", 1),
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
    _s("Seringues 1 ml", "حقن 1 مل", "injection", "boite", 2),
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
