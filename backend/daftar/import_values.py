"""Rules for the values of an imported spreadsheet (section 14) – pure functions, no database.

Amounts (``parse_millimes``) – one clear rule, in dinars:
- spaces (also non-breaking/thin) separate thousands; a currency label (DT, TND, د.ت) may follow;
- with both "." and "," the **last** one is the decimal separator, the other separates thousands;
- a single separator that occurs **once** is always the decimal separator (Tunisian notation: "12,500" and
  "12.500" are 12.5 DT, "1.250" is 1.25 DT); one that occurs several times separates thousands;
- thousands groups have exactly 3 digits; text with more than 3 decimals is refused (never rounded silently);
- numeric Excel cells (floats) are rounded half-up to the millime; negative amounts and amounts above
  100 000 DT are refused; 0 is 0 (the caller creates no balance for it).

Dates: Excel serial numbers (1910–2099), ``dd/mm/yyyy`` (or ``mm/dd/yyyy`` with the option ``mdy``),
``yyyy-mm-dd``, 2-digit years (≤ this year → 20yy, else 19yy), separators ``/ - .``, an optional time after it.
Phones: numbers from Excel (``20123456.0``, ``2.0123456E7``, ``21620123456`` without its leading ``00``) are
repaired; with several numbers in one cell the first valid one counts.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal

from .money import MAX_MILLIMES
from .phone import InvalidPhone, normalize_phone

NameOrder = Literal["last_first", "first_last"]
DateFormat = Literal["dmy", "mdy", "ymd"]

EXCEL_EPOCH = date(1899, 12, 30)
#: Plausible Excel serial numbers: 01.01.1910 … 31.12.2099 (smaller numbers are not dates).
SERIAL_MIN, SERIAL_MAX = 3654, 73050
MIN_DURATION, MAX_DURATION = 5, 480


class ImportValueError(ValueError):
    """A cell that cannot be used; the message (French) goes into the report."""


def norm(text: Any) -> str:
    """Lower case without accents, Arabic diacritics, spaces and punctuation – for comparing headers and words."""
    t = unicodedata.normalize("NFKD", str(text)).lower().replace("ـ", "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-zء-ي]+", "", t)


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def as_text(value: Any) -> str:
    """A cell as text: integral numbers without ``.0``, dates as ``dd/mm/yyyy``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M") if (value.hour, value.minute) != (0, 0) else value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return " ".join(str(value).split())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


# --- amounts ---------------------------------------------------------------------------------------------------

_CURRENCY = re.compile(r"\s*(?:dt|tnd|dinars?|د\.?\s*ت\.?)\s*$", re.IGNORECASE)


def parse_millimes(raw: Any) -> int | None:
    if is_blank(raw):
        return None
    if isinstance(raw, bool):
        raise ImportValueError("Montant invalide.")
    if isinstance(raw, int):
        millimes = raw * 1000
    elif isinstance(raw, float):
        if not math.isfinite(raw):
            raise ImportValueError("Montant invalide.")
        millimes = int((Decimal(repr(raw)) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    else:
        millimes = _text_millimes(str(raw))
    if millimes < 0:
        raise ImportValueError("Montant négatif refusé.")
    if millimes > MAX_MILLIMES:
        raise ImportValueError("Montant supérieur à 100 000 DT.")
    return millimes


def _text_millimes(raw: str) -> int:
    t = _CURRENCY.sub("", raw.strip())
    for space in (" ", " ", " "):
        t = t.replace(space, " ")
    t = t.strip().removeprefix("+").strip()
    if t.startswith("-"):
        raise ImportValueError("Montant négatif refusé.")
    if not re.fullmatch(r"[0-9 .,]+", t) or not any(ch.isdigit() for ch in t):
        raise ImportValueError("Montant invalide.")
    decimal_sep = thousands_sep = None
    if "." in t and "," in t:
        decimal_sep = "." if t.rindex(".") > t.rindex(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
    elif "." in t or "," in t:
        sep = "." if "." in t else ","
        if t.count(sep) == 1:
            decimal_sep = sep
        else:
            thousands_sep = sep
    whole, _, fraction = t.partition(decimal_sep) if decimal_sep else (t, "", "")
    if decimal_sep and (not fraction.isdigit()):
        raise ImportValueError("Montant invalide.")
    if len(fraction) > 3:
        raise ImportValueError("Montant avec plus de 3 décimales.")
    groups = re.split(f"[ {re.escape(thousands_sep)}]" if thousands_sep else " ", whole.strip())
    if any(not g.isdigit() for g in groups) or any(len(g) != 3 for g in groups[1:]) or (len(groups) > 1 and len(groups[0]) > 3):
        raise ImportValueError("Montant invalide.")
    return int("".join(groups)) * 1000 + int(fraction.ljust(3, "0") or 0)


# --- dates and times -------------------------------------------------------------------------------------------

_YMD = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](.*))?$")
_DMY = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?:[ T](.*))?$")
_SERIAL = re.compile(r"^\d+(?:\.\d+)?$")
_TIME = re.compile(r"^(\d{1,2})\s*[:hH.]\s*(\d{2})?(?::(\d{2}))?$")


def _serial_date(number: float) -> date:
    if not SERIAL_MIN <= number <= SERIAL_MAX + 0.99999:
        raise ImportValueError("Date invalide.")
    return EXCEL_EPOCH + timedelta(days=int(number))


def _split_date(raw: str, fmt: DateFormat, today: date) -> tuple[date, str | None]:
    t = " ".join(raw.split())
    try:
        if m := _YMD.match(t):
            return date(int(m[1]), int(m[2]), int(m[3])), m[4]
        if m := _DMY.match(t):
            first, second, year = int(m[1]), int(m[2]), m[3]
            y = int(year)
            if len(year) == 2:
                y += 2000 if y <= today.year % 100 else 1900
            day, month = (second, first) if fmt == "mdy" else (first, second)
            return date(y, month, day), m[4]
    except ValueError:
        raise ImportValueError("Date invalide.") from None
    raise ImportValueError("Date invalide (jj/mm/aaaa).")


def parse_date(raw: Any, fmt: DateFormat, *, today: date) -> date | None:
    if is_blank(raw):
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if _is_number(raw):
        return _serial_date(raw)
    text = str(raw).strip()
    if _SERIAL.fullmatch(text):
        return _serial_date(float(text))
    return _split_date(text, fmt, today)[0]


def parse_time(raw: Any) -> time | None:
    if is_blank(raw):
        return None
    if isinstance(raw, datetime):
        return raw.time().replace(second=0, microsecond=0)
    if isinstance(raw, time):
        return raw.replace(second=0, microsecond=0)
    if _is_number(raw):
        if not 0 <= raw < 1:
            raise ImportValueError("Heure invalide.")
        minutes = round(raw * 24 * 60)
        if minutes >= 24 * 60:
            raise ImportValueError("Heure invalide.")
        return time(minutes // 60, minutes % 60)
    m = _TIME.fullmatch(str(raw).strip())
    if not m:
        raise ImportValueError("Heure invalide (HH:MM).")
    hour, minute = int(m[1]), int(m[2] or 0)
    if hour > 23 or minute > 59:
        raise ImportValueError("Heure invalide (HH:MM).")
    return time(hour, minute)


def parse_datetime(raw: Any, fmt: DateFormat, *, today: date) -> datetime | None:
    """A naive local (Tunis) date and time."""
    if is_blank(raw):
        return None
    if isinstance(raw, datetime):
        return raw.replace(second=0, microsecond=0, tzinfo=None)
    if _is_number(raw) or _SERIAL.fullmatch(str(raw).strip()):
        number = float(raw)
        day = _serial_date(number)
        return datetime.combine(day, parse_time(number - int(number)) or time(0, 0))
    day, rest = _split_date(str(raw).strip(), fmt, today)
    moment = parse_time(rest) if rest else None
    if moment is None:
        raise ImportValueError("Heure manquante.")
    return datetime.combine(day, moment)


def parse_duration(raw: Any) -> int | None:
    if is_blank(raw):
        return None
    if _is_number(raw):
        if not float(raw).is_integer():
            raise ImportValueError("Durée invalide (minutes).")
        minutes = int(raw)
    else:
        t = str(raw).strip().lower().replace(" ", "")
        if m := re.fullmatch(r"(\d+)(?:min|mn|minutes?|m)?", t):
            minutes = int(m[1])
        elif m := re.fullmatch(r"(\d+)[h:](\d{2})?", t):
            minutes = int(m[1]) * 60 + int(m[2] or 0)
        else:
            raise ImportValueError("Durée invalide (minutes).")
    if not MIN_DURATION <= minutes <= MAX_DURATION:
        raise ImportValueError("Durée entre 5 et 480 minutes.")
    return minutes


def parse_year(raw: Any, *, today: date) -> int | None:
    if is_blank(raw):
        return None
    text = as_text(raw) if _is_number(raw) else str(raw).strip()
    if not re.fullmatch(r"\d{4}", text) or not 1900 <= int(text) <= today.year:
        raise ImportValueError("Année de naissance invalide.")
    return int(text)


# --- phones, names, yes/no, language ---------------------------------------------------------------------------

_NUMERIC = re.compile(r"^\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")


def parse_phone(raw: Any) -> str | None:
    if is_blank(raw):
        return None
    if isinstance(raw, bool):
        raise ImportValueError("Numéro de téléphone invalide.")
    if _is_number(raw):
        if not float(raw).is_integer():
            raise ImportValueError("Numéro de téléphone invalide.")
        text = str(int(raw))
    else:
        text = str(raw).strip()
        if _NUMERIC.fullmatch(text) and ("." in text or "e" in text.lower()):
            try:
                number = Decimal(text)
            except InvalidOperation:
                raise ImportValueError("Numéro de téléphone invalide.") from None
            if number != number.to_integral_value():
                raise ImportValueError("Numéro de téléphone invalide.")
            text = str(int(number))
    for candidate in re.split(r"[/;,|]|\s{2,}", text):
        try:
            return normalize_phone(candidate)
        except InvalidPhone:
            continue
    raise ImportValueError("Numéro de téléphone invalide.")


def clean_name(raw: Any) -> str:
    return " ".join(as_text(raw).split())


def split_full_name(full: str, order: NameOrder) -> tuple[str, str]:
    """``(first, last)``; "Nom Prénom" (``last_first``): the last word is the first name ("Ben Ali Amira")."""
    words = full.split()
    if len(words) < 2:
        raise ImportValueError("Nom complet incomplet (nom et prénom attendus).")
    if order == "first_last":
        return words[0], " ".join(words[1:])
    return words[-1], " ".join(words[:-1])


_YES = {"oui", "o", "yes", "y", "x", "1", "true", "vrai", "ok", "نعم"}
_NO = {"non", "n", "no", "0", "false", "faux", "لا"}


def parse_bool(raw: Any) -> bool | None:
    if is_blank(raw):
        return None
    if isinstance(raw, bool):
        return raw
    if _is_number(raw) and raw in (0, 1):
        return bool(raw)
    word = norm(raw) or str(raw).strip().lower()
    if word in _YES:
        return True
    if word in _NO:
        return False
    raise ImportValueError("Valeur oui/non invalide.")


_FR = {"fr", "francais", "french", "f", "فرنسية", "الفرنسية"}
_AR = {"ar", "arabe", "arabic", "a", "عربي", "عربية", "العربية"}


def parse_lang(raw: Any) -> str | None:
    if is_blank(raw):
        return None
    word = norm(raw)
    if word in _FR:
        return "fr"
    if word in _AR:
        return "ar"
    raise ImportValueError("Langue inconnue (fr ou ar).")


# --- header suggestion -----------------------------------------------------------------------------------------

#: Daftar fields → header words (normalised with :func:`norm`). Fields of both import kinds.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "fullName": ("nomcomplet", "nometprenom", "nomprenom", "prenometnom", "prenomnom", "nompatient", "patient",
                 "fullname", "name", "patientname", "الاسمواللقب", "اللقبوالاسم", "الاسمالكامل", "المريض", "اسمالمريض"),
    "lastName": ("nom", "nomdefamille", "nomfamille", "lastname", "surname", "familyname", "اللقب", "لقب",
                 "اسمالعائلة", "الاسمالعائلي"),
    "firstName": ("prenom", "firstname", "givenname", "الاسم", "اسم"),
    "phone": ("tel", "telephone", "gsm", "mobile", "portable", "phone", "numerotelephone", "numtel", "ntel", "notel",
              "telportable", "cellulaire", "الهاتف", "هاتف", "رقمالهاتف", "الجوال", "جوال", "الرقم"),
    "birthDate": ("datedenaissance", "datenaissance", "naissance", "ddn", "nele", "nee", "birthdate", "dateofbirth",
                  "dob", "تاريخالولادة", "تاريخالميلاد"),
    "birthYear": ("anneedenaissance", "anneenaissance", "annee", "birthyear", "yearofbirth", "سنةالولادة", "سنةالميلاد"),
    "notes": ("notes", "note", "remarque", "remarques", "observation", "observations", "commentaire", "commentaires",
              "comment", "comments", "ملاحظات", "ملاحظة"),
    "alerts": ("alerte", "alertes", "allergie", "allergies", "antecedents", "alert", "alerts", "medicalalert",
               "حساسية", "تنبيه", "تنبيهات", "سوابق"),
    "lang": ("langue", "lang", "language", "لغة", "اللغة"),
    "reminderConsent": ("rappel", "rappels", "rappelsms", "consentement", "sms", "whatsapp", "consent", "reminder",
                        "reminders", "تذكير", "موافقة"),
    "openingBalance": ("solde", "reste", "resteapayer", "credit", "dette", "du", "montantdu", "impaye", "impayes",
                       "balance", "openingbalance", "المتبقي", "الباقي", "الدين", "المبلغالمتبقي"),
    "externalRef": ("ref", "reference", "ndossier", "numerodossier", "dossier", "nodossier", "id", "code", "matricule",
                    "n", "no", "numero", "رقمالملف", "ملف"),
    "date": ("date", "jour", "daterdv", "datedurendezvous", "daterendezvous", "التاريخ", "اليوم"),
    "time": ("heure", "horaire", "time", "hour", "heurerdv", "الساعة", "الوقت"),
    "datetime": ("dateheure", "dateetheure", "rendezvous", "rdv", "datetime", "start", "debut", "موعد", "الموعد"),
    "durationMin": ("duree", "duration", "minutes", "min", "dureemin", "المدة"),
    "endTime": ("fin", "heurefin", "heuredefin", "end", "endtime", "النهاية"),
    "service": ("acte", "actes", "motif", "prestation", "service", "typedeconsultation", "type", "soin", "soins",
                "consultation", "الخدمة", "نوع", "الفحص"),
    "practitioner": ("praticien", "medecin", "docteur", "dr", "practitioner", "doctor", "therapeute", "kine",
                     "الطبيب", "المعالج"),
}
FIELDS = tuple(SYNONYMS)
#: Order of the second ("header contains the word") pass: the more specific fields first.
_CONTAINS_ORDER = ("firstName", "fullName", "birthDate", "birthYear", "phone", "openingBalance", "reminderConsent",
                   "alerts", "notes", "lang", "externalRef", "datetime", "durationMin", "endTime", "time", "date",
                   "service", "practitioner", "lastName")


def suggest_mapping(headers: list[str]) -> dict[str, int | None]:
    """Field → column index guessed from the headers (FR/AR/EN); every column and field is used at most once."""
    names = [norm(h) for h in headers]
    mapping: dict[str, int | None] = dict.fromkeys(FIELDS)
    used: set[int] = set()
    for index, name in enumerate(names):
        for field in FIELDS:
            if mapping[field] is None and name in SYNONYMS[field]:
                mapping[field] = index
                used.add(index)
                break
    for index, name in enumerate(names):
        if index in used or not name:
            continue
        for field in _CONTAINS_ORDER:
            if mapping[field] is None and any(len(word) >= 4 and word in name for word in SYNONYMS[field]):
                mapping[field] = index
                used.add(index)
                break
    return mapping
