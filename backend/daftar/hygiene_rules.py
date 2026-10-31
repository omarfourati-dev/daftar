"""When a hygiene or maintenance task is due (spec stock-hygiène 5.1) – rules without a database.

A task has a rhythm (:class:`Rhythm`) that starts on ``starts_on`` (the first due date):

- ``daily``: every opening day of the practice (weekly hours, no closure) – nobody purges a closed practice;
- ``weekly``: every week on ``weekday`` (ISO, 1 = Monday);
- ``monthly``: every month on the day of ``starts_on`` – the last day of shorter months;
- ``yearly``: every year on the date of ``starts_on`` (29 February → 28 February in other years);
- ``every_n_days``: every ``interval_days`` days by the calendar.

The **current occurrence** (:func:`last_due`) is the latest due date up to today. It is "à faire" on its day and
"en retard" afterwards, until it is done or the next occurrence replaces it – a missed purge of yesterday is not
carried along (today's counts), a missed weekly autoclave test stays red until it is done or next week's is due.
The history (:func:`occurrences`) lists every due date, so gaps stay visible.

Start plans (:func:`starter_plan`, section 5.1): typical equipment and tasks per specialty, FR and AR – created only
when the practice asks for them. Texts document; they never promise a legal conformity.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

Frequency = Literal["daily", "weekly", "monthly", "yearly", "every_n_days"]
FREQUENCIES: tuple[Frequency, ...] = ("daily", "weekly", "monthly", "yearly", "every_n_days")
EquipmentKind = Literal[
    "autoclave", "thermodesinfecteur", "ultrasons", "compresseur", "aspiration", "fauteuil", "radiographie", "autre",
]
EQUIPMENT_KINDS: tuple[EquipmentKind, ...] = (
    "autoclave", "thermodesinfecteur", "ultrasons", "compresseur", "aspiration", "fauteuil", "radiographie", "autre",
)
#: How far back the current occurrence is looked for (a yearly task plus a leap day).
LOOK_BACK_DAYS = 400

OpenDay = Callable[[date], bool]


@dataclass(frozen=True)
class Rhythm:
    frequency: Frequency
    starts_on: date
    weekday: int | None = None
    interval_days: int | None = None

    def __post_init__(self) -> None:
        if (self.frequency == "weekly") != (self.weekday is not None):
            raise ValueError("invalid_rhythm: Choisissez le jour de la semaine (seulement pour « chaque semaine »).")
        if self.weekday is not None and not 1 <= self.weekday <= 7:
            raise ValueError("invalid_rhythm: Jour de la semaine invalide.")
        if (self.frequency == "every_n_days") != (self.interval_days is not None):
            raise ValueError("invalid_rhythm: Indiquez le nombre de jours (seulement pour « tous les N jours »).")
        if self.interval_days is not None and not 2 <= self.interval_days <= 365:
            raise ValueError("invalid_rhythm: Entre 2 et 365 jours.")


def _same_day_of_month(anchor: date, day: date) -> bool:
    last = calendar.monthrange(day.year, day.month)[1]
    return day.day == min(anchor.day, last)


def is_due(rhythm: Rhythm, day: date, open_day: OpenDay) -> bool:
    if day < rhythm.starts_on:
        return False
    match rhythm.frequency:
        case "daily":
            return open_day(day)
        case "weekly":
            return day.isoweekday() == rhythm.weekday
        case "monthly":
            return _same_day_of_month(rhythm.starts_on, day)
        case "yearly":
            return day.month == rhythm.starts_on.month and _same_day_of_month(rhythm.starts_on, day)
        case "every_n_days":
            assert rhythm.interval_days is not None
            return (day - rhythm.starts_on).days % rhythm.interval_days == 0
    return False


def _days(first: date, last: date) -> Iterator[date]:
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def occurrences(rhythm: Rhythm, first: date, last: date, open_day: OpenDay) -> list[date]:
    """Every due date in ``[first, last]``."""
    return [d for d in _days(max(first, rhythm.starts_on), last) if is_due(rhythm, d, open_day)]


def last_due(rhythm: Rhythm, today: date, open_day: OpenDay) -> date | None:
    """The current occurrence: the latest due date up to ``today`` (None before the first one)."""
    stop = max(rhythm.starts_on, today - timedelta(days=LOOK_BACK_DAYS))
    day = today
    while day >= stop:
        if is_due(rhythm, day, open_day):
            return day
        day -= timedelta(days=1)
    return None


def next_due(rhythm: Rhythm, after: date, open_day: OpenDay) -> date | None:
    """The first due date after ``after`` (within a bit more than a year)."""
    for day in _days(max(after + timedelta(days=1), rhythm.starts_on), max(after, rhythm.starts_on) + timedelta(days=LOOK_BACK_DAYS)):
        if is_due(rhythm, day, open_day):
            return day
    return None


# --- start plans (section 5.1) -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StarterEquipment:
    key: str
    name_fr: str
    name_ar: str
    kind: EquipmentKind


@dataclass(frozen=True)
class StarterTask:
    title_fr: str
    title_ar: str
    frequency: Frequency
    equipment: str | None = None
    weekday: int | None = None
    interval_days: int | None = None
    instructions_fr: str = ""
    instructions_ar: str = ""


@dataclass(frozen=True)
class StarterPlan:
    equipment: tuple[StarterEquipment, ...] = field(default_factory=tuple)
    tasks: tuple[StarterTask, ...] = field(default_factory=tuple)


SURFACES = StarterTask("Désinfection des surfaces", "تطهير الأسطح", "daily",
                       instructions_fr="Plans de travail, poignées, table ou fauteuil, entre les patients et le soir.",
                       instructions_ar="أسطح العمل والمقابض وطاولة الفحص أو الكرسي، بين المرضى وفي المساء.")
EXPIRY_CHECK = StarterTask("Vérification des dates de péremption", "التثبت من تواريخ انتهاء الصلاحية", "monthly")

DENTIST = StarterPlan(
    equipment=(
        StarterEquipment("autoclave", "Autoclave", "جهاز التعقيم (أوتوكلاف)", "autoclave"),
        StarterEquipment("fauteuil", "Fauteuil", "كرسي الأسنان", "fauteuil"),
        StarterEquipment("aspiration", "Aspiration", "جهاز الشفط", "aspiration"),
        StarterEquipment("ultrasons", "Bac à ultrasons", "حوض الموجات فوق الصوتية", "ultrasons"),
        StarterEquipment("compresseur", "Compresseur", "الضاغط", "compresseur"),
        StarterEquipment("radio", "Radiographie", "جهاز الأشعة", "radiographie"),
    ),
    tasks=(
        StarterTask("Purge des conduits du fauteuil", "تطهير قنوات كرسي الأسنان", "daily", "fauteuil",
                    instructions_fr="Le matin avant le premier patient, puis quelques secondes entre deux patients.",
                    instructions_ar="صباحًا قبل أول مريض، ثم بضع ثوانٍ بين مريضين."),
        StarterTask("Nettoyage de l’aspiration", "تنظيف جهاز الشفط", "daily", "aspiration",
                    instructions_fr="Aspirer la solution de nettoyage en fin de journée.",
                    instructions_ar="شفط محلول التنظيف في آخر اليوم."),
        StarterTask("Changement de la solution du bac à ultrasons", "تغيير محلول حوض الموجات فوق الصوتية", "daily", "ultrasons"),
        SURFACES,
        StarterTask("Test Bowie-Dick / Hélix de l’autoclave", "اختبار بووي-ديك / هيليكس لجهاز التعقيم", "weekly", "autoclave",
                    weekday=1, instructions_fr="Premier cycle de la semaine, à vide. Notez « non conforme » si l’indicateur ne vire pas.",
                    instructions_ar="أول دورة في الأسبوع، دون حمولة. سجّلوا «غير مطابق» إذا لم يتغيّر لون المؤشر."),
        StarterTask("Purge du compresseur", "تفريغ الضاغط", "weekly", "compresseur", weekday=5),
        EXPIRY_CHECK,
        StarterTask("Maintenance de l’autoclave", "صيانة جهاز التعقيم", "yearly", "autoclave"),
        StarterTask("Contrôle de radioprotection", "مراقبة الوقاية من الإشعاع", "yearly", "radio"),
    ),
)
GENERALIST = StarterPlan(
    equipment=(
        StarterEquipment("frigo", "Réfrigérateur à vaccins", "ثلاجة اللقاحات", "autre"),
        StarterEquipment("tensiometre", "Tensiomètre", "جهاز قيس الضغط", "autre"),
    ),
    tasks=(
        StarterTask("Désinfection de la table d’examen", "تطهير طاولة الفحص", "daily",
                    instructions_fr="Changer le drap d’examen entre les patients.", instructions_ar="تغيير غطاء الطاولة بين المرضى."),
        SURFACES,
        StarterTask("Relevé de température du réfrigérateur à vaccins", "تسجيل حرارة ثلاجة اللقاحات", "daily", "frigo",
                    instructions_fr="Entre +2 et +8 °C. Notez la température dans la note.",
                    instructions_ar="بين 2+ و8+ درجات. سجّلوا الحرارة في الملاحظة."),
        StarterTask("Contrôle du chariot d’urgence", "مراقبة عربة الطوارئ", "weekly", weekday=1),
        EXPIRY_CHECK,
        StarterTask("Étalonnage du tensiomètre", "معايرة جهاز قيس الضغط", "yearly", "tensiometre"),
    ),
)
MEDICAL = StarterPlan(
    equipment=(StarterEquipment("appareils", "Appareils de consultation", "أجهزة الفحص", "autre"),),
    tasks=(
        StarterTask("Désinfection de la table d’examen", "تطهير طاولة الفحص", "daily"),
        SURFACES,
        StarterTask("Contrôle de la trousse d’urgence", "مراقبة حقيبة الطوارئ", "weekly", weekday=1),
        EXPIRY_CHECK,
        StarterTask("Maintenance des appareils", "صيانة الأجهزة", "yearly", "appareils"),
    ),
)
PHYSIO = StarterPlan(
    equipment=(StarterEquipment("electro", "Appareil d’électrothérapie", "جهاز العلاج الكهربائي", "autre"),),
    tasks=(
        StarterTask("Désinfection des tables de soin", "تطهير طاولات العلاج", "daily"),
        SURFACES,
        StarterTask("Lavage du linge (draps, serviettes)", "غسل البياضات (أغطية، مناشف)", "weekly", weekday=6),
        StarterTask("Contrôle des électrodes et des câbles", "مراقبة الأقطاب والأسلاك", "monthly", "electro"),
        StarterTask("Maintenance de l’appareil d’électrothérapie", "صيانة جهاز العلاج الكهربائي", "yearly", "electro"),
    ),
)
GENERIC = StarterPlan(
    tasks=(
        SURFACES,
        StarterTask("Nettoyage approfondi de la salle d’attente", "تنظيف معمّق لقاعة الانتظار", "weekly", weekday=6),
        StarterTask("Vérification de la trousse de premiers secours", "التثبت من حقيبة الإسعافات الأولية", "monthly"),
    ),
)
PLANS: dict[str, StarterPlan] = {
    "dentiste": DENTIST, "generaliste": GENERALIST, "pediatre": GENERALIST, "kinesitherapeute": PHYSIO,
    "gynecologue": MEDICAL, "dermatologue": MEDICAL, "ophtalmologue": MEDICAL, "cardiologue": MEDICAL, "orl": MEDICAL,
}


def starter_plan(specialty: str) -> StarterPlan:
    return PLANS.get(specialty, GENERIC)
