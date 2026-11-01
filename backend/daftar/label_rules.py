"""Rules of the sterilisation and specimen labels (spec stock-hygiène 5.3, 6, 7) – no database here.

- A **pack code** names autoclave, cycle and pack: ``A3-0412-07`` (the autoclave's label code, the cycle number with at
  least four digits, the pack with two). Codes use capitals, digits and ``-`` only – the QR code stays in the small
  alphanumeric mode and a desk scanner (keyboard wedge) types it as printed.
- A **specimen code** names one tube of one print: ``E1042-03`` (the print's number, the tube).
- A pack is **sterile until** the day before its "à utiliser avant" date: ``expires_on`` = sterilised + shelf life,
  and from that day on it is ``expired``. A cycle found "non conforme" (also later, by a correction) makes every one of
  its packs ``not_sterile``.
- **Settings** of a practice (``practice.label_settings``): the format per kind of label and the shelf life per
  packaging. Daftar proposes 90 days everywhere; the practice sets its own protocol (Daftar documents, it does not
  prescribe – spec 2, anti-goals).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

LabelFormat = Literal["roll62", "label57x32", "a4_3x8"]
LabelKind = Literal["sterile", "specimen"]
Packaging = Literal["sachet", "double_sachet", "conteneur", "champ"]
SpecimenKind = Literal["edta", "sec", "citrate", "heparine", "urine", "selles", "frottis", "autre"]
PackState = Literal["usable", "expired", "used", "not_sterile"]

#: Brother QL roll 62 mm (cut at 29 mm), Dymo/Zebra 57 × 32 mm, A4 sheet of 3 × 8 labels of 70 × 37 mm.
LABEL_FORMATS: tuple[LabelFormat, ...] = ("roll62", "label57x32", "a4_3x8")
LABEL_KINDS: tuple[LabelKind, ...] = ("sterile", "specimen")
PACKAGINGS: tuple[Packaging, ...] = ("sachet", "double_sachet", "conteneur", "champ")
SPECIMEN_KINDS: tuple[SpecimenKind, ...] = ("edta", "sec", "citrate", "heparine", "urine", "selles", "frottis", "autre")
DEFAULT_SHELF_LIFE_DAYS = 90
MAX_SHELF_LIFE_DAYS = 1825
#: Packs of one cycle (two digits on the label) and labels of one specimen print.
MAX_PACKS = 99
MAX_SPECIMEN_LABELS = 48
MAX_LABEL_CODES = 99

#: Programs offered for a new cycle (the practice's own last programs come first).
DEFAULT_PROGRAMS = ("134 °C – 18 min", "134 °C – 3,5 min", "121 °C – 20 min")

TITLES = frozenset({"dr", "dr.", "pr", "pr.", "docteur", "prof", "prof.", "mme", "mme.", "m.", "mr", "mr.", "د", "د."})


def pack_code(label_code: str, number: int, seq: int) -> str:
    return f"{label_code}-{number:04d}-{seq:02d}"


def specimen_code(print_id: int, tube: int) -> str:
    return f"E{print_id}-{tube:02d}"


def next_label_code(taken: list[str]) -> str:
    """The first free ``A<n>`` of a practice (``A1`` for its first autoclave)."""
    used = set(taken)
    for n in range(1, MAX_LABEL_CODES + 1):
        if f"A{n}" not in used:
            return f"A{n}"
    raise ValueError("no free autoclave code")


def initials(name: str) -> str:
    """``Dr. Amira Ben Salem`` → ``ABS``: the first letter of each word without the title, at most three."""
    words = [w for w in name.split() if w.lower() not in TITLES]
    return "".join(w[0] for w in words)[:3].upper()


def sterile_until(sterilised_on: date, shelf_life_days: int) -> date:
    """The "à utiliser avant" date: the pack is usable up to the day before."""
    return sterilised_on + timedelta(days=shelf_life_days)


def pack_state(*, result: str, used: bool, expires_on: date, today: date) -> PackState:
    if result != "ok":
        return "not_sterile"
    if used:
        return "used"
    if today >= expires_on:
        return "expired"
    return "usable"


@dataclass(frozen=True)
class PackQuery:
    """What the desk typed, read as a pack code: the full code when complete, else its parts."""

    code: str | None
    device: str | None
    number: int
    seq: int | None


_QUERY = re.compile(r"^(?:([A-Z]\d{1,2})-)?(\d{1,6})(?:-(\d{1,2}))?$")


def pack_query(text: str) -> PackQuery | None:
    """``a3 0412 07`` → the code ``A3-0412-07``; ``412-7`` → cycle 412, pack 7 of any autoclave; else None (free text)."""
    normalized = re.sub(r"[\s\-./_]+", "-", text.strip().upper()).strip("-")
    match = _QUERY.fullmatch(normalized)
    if match is None:
        return None
    device, number, seq = match.group(1), int(match.group(2)), match.group(3)
    seq_no = int(seq) if seq is not None else None
    code = pack_code(device, number, seq_no) if device and seq_no is not None else None
    return PackQuery(code=code, device=device, number=number, seq=seq_no)


def label_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """The stored settings completed with the defaults (unknown or invalid values fall back to them)."""
    raw = raw or {}
    formats = raw.get("formats") if isinstance(raw.get("formats"), dict) else {}
    days = raw.get("shelf_life_days") if isinstance(raw.get("shelf_life_days"), dict) else {}

    def shelf(packaging: str) -> int:
        value = days.get(packaging)
        valid = isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_SHELF_LIFE_DAYS
        return value if valid else DEFAULT_SHELF_LIFE_DAYS

    return {
        "formats": {kind: formats.get(kind) if formats.get(kind) in LABEL_FORMATS else "roll62" for kind in LABEL_KINDS},
        "shelf_life_days": {p: shelf(p) for p in PACKAGINGS},
    }


# --- templates of the pack contents per specialty (FR, AR) -----------------------------------------------------------

_DENTIST = (
    ("Kit examen", "طقم الفحص"),
    ("Kit extraction", "طقم القلع"),
    ("Kit détartrage", "طقم إزالة الجير"),
    ("Kit soins / composite", "طقم العلاج / الحشو"),
    ("Kit endodontie", "طقم علاج العصب"),
    ("Kit chirurgie", "طقم الجراحة"),
    ("Fraises", "سنابل الحفر"),
)
_MINOR_SURGERY = ("Kit petite chirurgie", "طقم الجراحة الصغرى")
_DRESSING = ("Kit pansement", "طقم الضماد")
_GENERAL = (
    _MINOR_SURGERY,
    ("Kit suture", "طقم الخياطة"),
    _DRESSING,
    ("Pince et ciseaux", "ملقط ومقص"),
)
_GYNECOLOGY = (
    ("Spéculum", "منظار مهبلي"),
    ("Kit frottis", "طقم المسحة"),
    ("Kit pose de stérilet", "طقم تركيب اللولب"),
    _MINOR_SURGERY,
)
_DERMATOLOGY = (
    ("Kit biopsie", "طقم الخزعة"),
    _MINOR_SURGERY,
    ("Curette", "مكشطة"),
    _DRESSING,
)
_OPHTHALMOLOGY = (
    ("Kit corps étranger", "طقم إزالة الأجسام الغريبة"),
    ("Blépharostat", "مبعد الجفون"),
    _MINOR_SURGERY,
)
_ENT = (
    ("Spéculums d’oreille", "منظار الأذن"),
    ("Kit lavage d’oreille", "طقم غسل الأذن"),
    ("Kit méchage nasal", "طقم حشو الأنف"),
)
_OTHER = (_MINOR_SURGERY, _DRESSING, ("Instruments", "أدوات"))
_CONTENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "dentiste": _DENTIST, "generaliste": _GENERAL, "pediatre": _GENERAL, "gynecologue": _GYNECOLOGY,
    "dermatologue": _DERMATOLOGY, "ophtalmologue": _OPHTHALMOLOGY, "orl": _ENT,
}


def pack_contents(specialty: str, lang: str) -> list[str]:
    """Typical contents of a pack of the specialty ("Kit examen", "Kit extraction" …) in the user's language."""
    pick = 1 if lang == "ar" else 0
    return [pair[pick] for pair in _CONTENTS.get(specialty, _OTHER)]
