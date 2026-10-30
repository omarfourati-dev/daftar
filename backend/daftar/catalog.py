"""Specialties (design section 12) and the default service catalog each new practice starts with.

Prices stay empty (the practice fills them in); ``online_bookable`` decides what patients can book online.
Use :func:`insert_default_services` when a practice is created (admin wizard, demo).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, insert

from .tables import service

Specialty = Literal[
    "generaliste", "dentiste", "pediatre", "gynecologue", "dermatologue", "ophtalmologue",
    "cardiologue", "orl", "kinesitherapeute", "psychologue", "autre",
]
SPECIALTIES: tuple[Specialty, ...] = (
    "generaliste", "dentiste", "pediatre", "gynecologue", "dermatologue", "ophtalmologue",
    "cardiologue", "orl", "kinesitherapeute", "psychologue", "autre",
)


@dataclass(frozen=True)
class CatalogItem:
    name_fr: str
    name_ar: str
    duration_min: int
    online_bookable: bool


def _i(name_fr: str, name_ar: str, minutes: int, online: bool) -> CatalogItem:
    return CatalogItem(name_fr, name_ar, minutes, online)


CONSULTATION_AR = "معاينة"
CONTROLE_AR = "مراقبة"

DEFAULT_CATALOGS: dict[str, tuple[CatalogItem, ...]] = {
    "generaliste": (
        _i("Consultation", CONSULTATION_AR, 20, True),
        _i("Contrôle", CONTROLE_AR, 15, True),
        _i("Certificat médical", "شهادة طبية", 10, True),
        _i("Vaccination", "تلقيح", 15, True),
        _i("Urgence", "حالة مستعجلة", 20, False),
    ),
    "dentiste": (
        _i("Consultation", CONSULTATION_AR, 30, True),
        _i("Contrôle", CONTROLE_AR, 20, True),
        _i("Détartrage", "إزالة الجير", 45, True),
        _i("Soin carie / composite", "علاج تسوّس / حشوة", 45, False),
        _i("Extraction", "قلع سنّ", 30, False),
        _i("Traitement de canal", "علاج العصب", 60, False),
        _i("Couronne – séance", "تاج – حصّة", 60, False),
        _i("Blanchiment", "تبييض الأسنان", 60, False),
        _i("Urgence / douleur", "حالة مستعجلة / ألم", 30, False),
    ),
    "pediatre": (
        _i("Consultation", CONSULTATION_AR, 30, True),
        _i("Suivi croissance", "متابعة النموّ", 20, True),
        _i("Vaccination", "تلقيح", 15, True),
        _i("Urgence", "حالة مستعجلة", 20, False),
    ),
    "gynecologue": (
        _i("Consultation", CONSULTATION_AR, 30, True),
        _i("Suivi de grossesse", "متابعة الحمل", 30, True),
        _i("Échographie", "تصوير بالصدى", 30, True),
        _i("Frottis", "مسحة عنق الرحم", 20, True),
        _i("Urgence", "حالة مستعجلة", 20, False),
    ),
    "dermatologue": (
        _i("Consultation", CONSULTATION_AR, 20, True),
        _i("Contrôle", CONTROLE_AR, 15, True),
        _i("Petite chirurgie", "جراحة صغرى", 45, False),
        _i("Acte esthétique", "علاج تجميلي", 45, False),
    ),
    "ophtalmologue": (
        _i("Consultation", CONSULTATION_AR, 20, True),
        _i("Contrôle", CONTROLE_AR, 15, True),
        _i("Fond d'œil", "فحص قاع العين", 20, False),
        _i("Bilan orthoptique", "تقييم تقويم البصر", 30, False),
    ),
    "cardiologue": (
        _i("Consultation", CONSULTATION_AR, 30, True),
        _i("Contrôle", CONTROLE_AR, 20, True),
        _i("ECG", "تخطيط القلب", 15, False),
        _i("Échocardiographie", "تصوير القلب بالصدى", 30, False),
        _i("Holter – pose", "تركيب جهاز هولتر", 15, False),
    ),
    "orl": (
        _i("Consultation", CONSULTATION_AR, 20, True),
        _i("Contrôle", CONTROLE_AR, 15, True),
        _i("Lavage d'oreilles", "غسل الأذن", 15, True),
        _i("Audiogramme", "قياس السمع", 30, False),
    ),
    "kinesitherapeute": (
        _i("Séance", "حصّة", 45, True),
        _i("Bilan", "تقييم", 60, True),
    ),
    "psychologue": (
        _i("Séance", "حصّة", 50, True),
        _i("Premier entretien", "مقابلة أولى", 60, True),
    ),
    "autre": (
        _i("Consultation", CONSULTATION_AR, 30, True),
        _i("Contrôle", CONTROLE_AR, 20, True),
    ),
}


def insert_default_services(conn: Connection, practice_id: int, specialty: str) -> int:
    """Adds the default catalog of ``specialty`` to a practice (prices empty); returns the number of services."""
    items = DEFAULT_CATALOGS[specialty]
    conn.execute(
        insert(service),
        [
            {
                "practice_id": practice_id,
                "name_fr": item.name_fr,
                "name_ar": item.name_ar,
                "duration_min": item.duration_min,
                "price_millimes": None,
                "online_bookable": item.online_bookable,
                "active": True,
                "sort": n,
            }
            for n, item in enumerate(items, start=1)
        ],
    )
    return len(items)
