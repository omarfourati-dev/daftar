"""``/api/labels`` – label settings and specimen labels (spec stock-hygiène 6, 7, 3, 8). The sterilisation labels come
with their cycle (:mod:`daftar.sterilization`); every label is printed by the web through the browser.

- ``GET /settings`` (staff) → ``{formats:{sterile, specimen}, shelfLifeDays:{sachet, double_sachet, conteneur, champ}}``
  · ``PATCH /settings`` (assistant, owner) – part of it; logged old → new (``label_settings``).
- ``POST /specimens {patientId, appointmentId?, items:[{kind, count, label?}], collectedAt?, collectedBy?}`` → 201
  Specimen print: every tube's label (patient NOM Prénom, birth date or year, kind, when, practice, code
  ``E<print>-<tube>``). It is also the proof: who printed, when, which tubes, how many – never a result. ``autre``
  needs its name (422 ``specimen_label_required``); at most 48 labels (422 ``too_many_labels``); collected at most a
  month ago and at most a day ahead (422 ``invalid_collected_at``). 422 ``invalid_patient`` / ``invalid_appointment``
  (an appointment of another patient too).
- ``GET /specimens?patientId=`` (staff) → the prints of a patient, newest first · ``GET /specimens/{id}`` → one print
  again (the labels with the patient's current name).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import Field, StrictInt
from sqlalchemy import Connection, exists, insert, select, update

from . import audit
from .deps import Conn, Ctx, StaffUser, StaffWriter
from .hygiene import HygieneManager
from .label_rules import (
    MAX_SHELF_LIFE_DAYS,
    MAX_SPECIMEN_LABELS,
    LabelFormat,
    Packaging,
    SpecimenKind,
    label_settings,
    specimen_code,
)
from .problems import not_found, unprocessable
from .schemas import ApiModel, InstantIn, TunisDateTime
from .tables import appointment, patient, practice, specimen_label_log

router = APIRouter(prefix="/api/labels", tags=["labels"])

ShelfLife = Annotated[StrictInt, Field(ge=1, le=MAX_SHELF_LIFE_DAYS)]
#: The change log names a setting by one key.
FORMAT_KEYS = {"sterile": "formatSterile", "specimen": "formatSpecimen"}
SHELF_KEYS = {"sachet": "shelfLifeSachet", "double_sachet": "shelfLifeDoubleSachet", "conteneur": "shelfLifeConteneur",
              "champ": "shelfLifeChamp"}


# --- settings -----------------------------------------------------------------------------------------------------


class Formats(ApiModel):
    sterile: LabelFormat
    specimen: LabelFormat


class SettingsOut(ApiModel):
    formats: Formats
    shelf_life_days: dict[Packaging, int]


class FormatsPatch(ApiModel):
    sterile: LabelFormat | None = None
    specimen: LabelFormat | None = None


class SettingsPatch(ApiModel):
    formats: FormatsPatch | None = None
    shelf_life_days: dict[Packaging, ShelfLife] | None = None


def load_settings(conn: Connection, practice_id: int) -> dict[str, Any]:
    raw = conn.execute(select(practice.c.label_settings).where(practice.c.id == practice_id)).scalar_one()
    return label_settings(raw)


def _out(settings: dict[str, Any]) -> SettingsOut:
    return SettingsOut(formats=Formats(**settings["formats"]), shelf_life_days=settings["shelf_life_days"])


@router.get("/settings")
def get_settings(user: StaffUser, conn: Conn) -> SettingsOut:
    return _out(load_settings(conn, user.pid))


@router.patch("/settings")
def patch_settings(body: SettingsPatch, user: HygieneManager, ctx: Ctx, conn: Conn) -> SettingsOut:
    current = load_settings(conn, user.pid)
    new = {"formats": dict(current["formats"]), "shelf_life_days": dict(current["shelf_life_days"])}
    if body.formats is not None:
        new["formats"].update(body.formats.model_dump(exclude_none=True, by_alias=False))
    if body.shelf_life_days:
        new["shelf_life_days"].update(body.shelf_life_days)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for group, keys in (("formats", FORMAT_KEYS), ("shelf_life_days", SHELF_KEYS)):
        for name, key in keys.items():
            if new[group][name] != current[group][name]:
                before[key], after[key] = current[group][name], new[group][name]
    if after:
        conn.execute(update(practice).where(practice.c.id == user.pid).values(label_settings=new))
        audit.record(conn, user, entity="label_settings", entity_id=user.pid, action="update", now=ctx.clock.now(),
                     before=before, after=after)
    return _out(new)


# --- specimen labels ----------------------------------------------------------------------------------------------


class SpecimenItem(ApiModel):
    kind: SpecimenKind
    count: Annotated[StrictInt, Field(ge=1, le=20)]
    label: Annotated[str, Field(max_length=30)] = ""


class SpecimenIn(ApiModel):
    patient_id: int
    appointment_id: int | None = None
    items: Annotated[list[SpecimenItem], Field(min_length=1, max_length=12)]
    collected_at: InstantIn | None = None
    collected_by: Annotated[str, Field(max_length=120)] = ""


class SpecimenPatient(ApiModel):
    id: int
    first_name: str
    last_name: str
    birth_date: date | None
    birth_year: int | None


class SpecimenLabel(ApiModel):
    code: str
    kind: SpecimenKind
    label: str


class SpecimenOut(ApiModel):
    id: int
    patient: SpecimenPatient
    appointment_id: int | None
    items: list[SpecimenItem]
    label_count: int
    labels: list[SpecimenLabel]
    collected_at: TunisDateTime
    collected_by: str
    printed_by: str
    printed_at: TunisDateTime


def _labels(print_id: int, items: list[dict[str, Any]]) -> list[SpecimenLabel]:
    labels: list[SpecimenLabel] = []
    for item in items:
        for _ in range(item["count"]):
            labels.append(SpecimenLabel(code=specimen_code(print_id, len(labels) + 1), kind=item["kind"],
                                        label=item.get("label", "")))
    return labels


def _specimen_rows(conn: Connection, practice_id: int, *conditions: Any) -> list[Any]:
    return list(conn.execute(
        select(specimen_label_log, patient.c.first_name, patient.c.last_name, patient.c.birth_date, patient.c.birth_year)
        .select_from(specimen_label_log.join(patient, patient.c.id == specimen_label_log.c.patient_id))
        .where(specimen_label_log.c.practice_id == practice_id, *conditions)
        .order_by(specimen_label_log.c.printed_at.desc(), specimen_label_log.c.id.desc())
    ).all())


def _specimen(row: Any) -> SpecimenOut:
    return SpecimenOut(
        id=row.id,
        patient=SpecimenPatient(id=row.patient_id, first_name=row.first_name, last_name=row.last_name,
                                birth_date=row.birth_date, birth_year=row.birth_year),
        appointment_id=row.appointment_id, items=[SpecimenItem(**i) for i in row.items], label_count=row.label_count,
        labels=_labels(row.id, row.items), collected_at=row.collected_at, collected_by=row.collected_by,
        printed_by=row.printed_by_name, printed_at=row.printed_at,
    )


def _check_target(conn: Connection, practice_id: int, body: SpecimenIn) -> None:
    known = conn.execute(select(exists().where(patient.c.id == body.patient_id,
                                               patient.c.practice_id == practice_id))).scalar_one()
    if not known:
        raise unprocessable("Patient introuvable dans le cabinet.", code="invalid_patient")
    if body.appointment_id is not None:
        found = conn.execute(select(exists().where(
            appointment.c.id == body.appointment_id, appointment.c.practice_id == practice_id,
            appointment.c.patient_id == body.patient_id))).scalar_one()
        if not found:
            raise unprocessable("Rendez-vous introuvable pour ce patient.", code="invalid_appointment")


@router.post("/specimens", status_code=201)
def print_specimens(body: SpecimenIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> SpecimenOut:
    now = ctx.clock.now()
    collected_at = body.collected_at or now
    if not now - timedelta(days=31) <= collected_at <= now + timedelta(days=1):
        raise unprocessable("Vérifiez la date du prélèvement.", code="invalid_collected_at")
    if any(i.kind == "autre" and not i.label for i in body.items):
        raise unprocessable("Nommez le prélèvement « Autre ».", code="specimen_label_required")
    total = sum(i.count for i in body.items)
    if total > MAX_SPECIMEN_LABELS:
        raise unprocessable(f"{MAX_SPECIMEN_LABELS} étiquettes au plus à la fois.", code="too_many_labels")
    _check_target(conn, user.pid, body)
    items = [{"kind": i.kind, "count": i.count, "label": i.label if i.kind == "autre" else ""} for i in body.items]
    new_id = conn.execute(
        insert(specimen_label_log).values(
            practice_id=user.pid, patient_id=body.patient_id, appointment_id=body.appointment_id, items=items,
            label_count=total, collected_at=collected_at, collected_by=body.collected_by, printed_by=user.user_id,
            printed_by_name=user.name[:120], printed_at=now,
        ).returning(specimen_label_log.c.id)
    ).scalar_one()
    return _specimen(_specimen_rows(conn, user.pid, specimen_label_log.c.id == new_id)[0])


@router.get("/specimens")
def list_specimens(
    user: StaffUser, conn: Conn, patient_id: Annotated[int, Query(alias="patientId")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SpecimenOut]:
    return [_specimen(r) for r in _specimen_rows(conn, user.pid, specimen_label_log.c.patient_id == patient_id)[:limit]]


@router.get("/specimens/{print_id}")
def get_specimens(print_id: int, user: StaffUser, conn: Conn) -> SpecimenOut:
    rows = _specimen_rows(conn, user.pid, specimen_label_log.c.id == print_id)
    if not rows:
        raise not_found()
    return _specimen(rows[0])


