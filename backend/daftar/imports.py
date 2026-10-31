"""Import of patients and appointments from Excel/CSV with the practice's own column mapping (section 14, E5).

Flow (owner and assistant; writing steps blocked with 402 while the subscription is suspended):
- ``POST /api/imports`` (multipart ``file``) → 201 ``{id, filename, sheets, sheet, headerRow, columns:[{index,
  header, samples}], rowCount, suggestedMapping}`` – the file is kept in ``import_job`` for 24 h at most; at most 3
  open (not committed) jobs per practice, a new upload deletes the oldest; 10 uploads per user and hour (429, failed
  ones count too); 403 ``demo_import_disabled`` in a demo practice (security review H1/H2);
- ``POST /api/imports/{id}/sheet {sheet, headerRow}`` → same shape (``headerRow`` 1-based, 0 = no header row);
- ``POST /api/imports/{id}/preview {kind, mapping:{field: column|null}, options}`` → counts, ``errors``,
  ``duplicates``, ``conflicts`` and 10 normalised rows – nothing is written;
- ``POST /api/imports/{id}/commit`` (same body) → ``{created, updated, skipped, errorCount, patientsCreated}`` in one
  transaction; the uploaded file is deleted at once, the problem list stays for ``GET /api/imports/{id}/report.csv``
  (``;``-separated UTF-8 with BOM, formula-like cells defused) until the job expires;
- ``GET/POST/DELETE /api/import-templates`` – saved mappings.

Counting: every non-empty data row ends up in exactly one of created / updated / skipped (duplicates, overlapping
appointments) / errorCount (rows with at least one unusable value).

Rules: a patient is the same when phone, last name and first name agree (case, accents and spaces ignored) – families
share phone numbers. Duplicates: ``skip`` (default), ``update`` (fills birth year, language, reminders, adds notes
and medical alerts that are not there yet – an alert is never replaced, one that does not fit into the 500 characters
is left out and named in the report (code review M3); the opening balance only once; a second line of the same
person in the file is a duplicate in the file, skipped – code review M2) or ``create``. An opening balance becomes the act "Reprise de solde".
Appointments: date + time (or one date-time column; one that holds only days takes the time column – code review M5;
two-digit years in the century nearest to today – N10), duration from the column, the end time, the service or the
practice default; the patient is found by phone + name (or by name alone when unique) and created when missing (then a
phone number is needed); past appointments are ``done``; appointments that overlap one of the practitioner (or
"no practitioner") or of the patient are not imported but listed. A row without practitioner in a practice with
active practitioners gets the only one, else the first one (practice order) free at that time (code review H1).
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import Field
from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .clock import TUNIS, today_tunis
from .context import AppContext
from .db import constraint_name
from .deps import Conn, Ctx, Principal, require_roles, require_writable
from .import_files import MAX_BYTES, MAX_COLUMNS, Book, ImportFileError, Table, read_table, read_workbook, samples
from .import_values import (
    DateFormat,
    ImportValueError,
    NameOrder,
    as_text,
    clean_name,
    is_blank,
    is_date_only,
    norm,
    parse_bool,
    parse_date,
    parse_datetime,
    parse_duration,
    parse_lang,
    parse_millimes,
    parse_phone,
    parse_time,
    parse_year,
    split_full_name,
    suggest_mapping,
)
from .onboarding import flag
from .problems import ApiError, conflict, forbidden, not_found, unprocessable
from .scheduling import active_practitioners
from .schemas import ApiModel, Lang, Name, TunisDateTime
from .tables import (
    FREEING_STATUSES,
    PATIENT_OVERLAP,
    PRACTITIONER_OVERLAP,
    appointment,
    import_job,
    import_template,
    patient,
    practice,
    practitioner,
    service,
    treatment,
)

router = APIRouter(prefix="/api/imports", tags=["imports"])
template_router = APIRouter(prefix="/api/import-templates", tags=["imports"])

JOB_TTL = timedelta(hours=24)
LIST_LIMIT = 500
SAMPLE_ROWS = 10
MAX_TEMPLATES = 100
#: Open (not committed) import jobs per practice – each keeps its file (up to 2 MB) for 24 h.
MAX_OPEN_JOBS = 3
#: Uploads per user and hour; every upload is parsed, failed ones too.
UPLOADS_PER_HOUR = 10
OPENING_BALANCE = "Reprise de solde"
#: Length of a patient's medical alerts (the API's limit too).
MAX_ALERTS = 500

Kind = Literal["patients", "appointments"]
PATIENT_FIELDS = ("lastName", "firstName", "fullName", "phone", "birthDate", "birthYear", "notes", "alerts", "lang",
                  "reminderConsent", "openingBalance", "externalRef")
APPOINTMENT_FIELDS = ("date", "time", "datetime", "durationMin", "endTime", "lastName", "firstName", "fullName",
                      "phone", "service", "practitioner", "notes")
FIELDS_BY_KIND: dict[str, tuple[str, ...]] = {"patients": PATIENT_FIELDS, "appointments": APPOINTMENT_FIELDS}
#: Field names in the report (French, like the rest of the generated files).
LABELS = {
    "lastName": "Nom", "firstName": "Prénom", "fullName": "Nom complet", "phone": "Téléphone",
    "birthDate": "Date de naissance", "birthYear": "Année de naissance", "notes": "Notes", "alerts": "Alertes médicales",
    "lang": "Langue", "reminderConsent": "Rappels", "openingBalance": "Solde", "externalRef": "Référence",
    "date": "Date", "time": "Heure", "datetime": "Date et heure", "durationMin": "Durée", "endTime": "Heure de fin",
    "service": "Acte", "practitioner": "Praticien", "duplicate": "Doublon", "overlap": "Horaire",
}

ImportReader = Annotated[Principal, Depends(require_roles("owner", "assistant"))]


def _import_writer(user: ImportReader) -> Principal:
    return require_writable(user)


ImportWriter = Annotated[Principal, Depends(_import_writer)]


# --- models ----------------------------------------------------------------------------------------------------

class ImportOptions(ApiModel):
    name_order: NameOrder = "last_first"
    date_format: DateFormat = "dmy"
    default_lang: Lang = "fr"
    reminder_consent: bool = False
    duplicates: Literal["skip", "update", "create"] = "skip"
    default_duration_min: Annotated[int, Field(ge=5, le=480)] | None = None


Mapping = Annotated[dict[str, int | None], Field(max_length=40)]


class ColumnOut(ApiModel):
    index: int
    header: str
    samples: list[str]


class ImportOut(ApiModel):
    id: uuid.UUID
    filename: str
    sheets: list[str]
    sheet: str
    header_row: int
    columns: list[ColumnOut]
    row_count: int
    suggested_mapping: dict[str, int | None]


class SheetIn(ApiModel):
    sheet: Annotated[str, Field(max_length=255)]
    header_row: Annotated[int, Field(ge=0, le=20)]


class MappingIn(ApiModel):
    kind: Kind
    mapping: Mapping
    options: ImportOptions = Field(default_factory=ImportOptions)


class RowProblem(ApiModel):
    row: int
    field: str
    message: str
    value: str


class Duplicate(ApiModel):
    row: int
    patient_id: int | None
    name: str


class Overlap(ApiModel):
    row: int
    starts_at: TunisDateTime
    message: str


class PreviewOut(ApiModel):
    will_create: int
    will_update: int
    will_skip: int
    will_create_patients: int
    error_count: int
    errors: list[RowProblem]
    duplicates: list[Duplicate]
    conflicts: list[Overlap]
    sample: list[dict[str, Any]]


class CommitOut(ApiModel):
    created: int
    updated: int
    skipped: int
    error_count: int
    patients_created: int


class TemplateIn(ApiModel):
    name: Name
    kind: Kind
    mapping: Mapping
    options: ImportOptions = Field(default_factory=ImportOptions)


class TemplateOut(TemplateIn):
    id: int
    created_at: TunisDateTime


# --- jobs ------------------------------------------------------------------------------------------------------

def _file_error(exc: ImportFileError) -> ApiError:
    return ApiError(exc.status, exc.message, code=exc.code)


def _clean_filename(name: str | None) -> str:
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[-255:] or "import"


def _job(conn: Connection, user: Principal, job_id: uuid.UUID, now: datetime, *, lock: bool = False) -> Any:
    query = select(import_job).where(
        import_job.c.id == job_id, import_job.c.practice_id == user.pid, import_job.c.expires_at > now
    )
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).first()
    if row is None:
        raise not_found()
    return row


def _open_job(conn: Connection, user: Principal, job_id: uuid.UUID, now: datetime) -> Any:
    job = _job(conn, user, job_id, now, lock=True)
    if job.committed_at is not None:
        raise conflict("Cet import a déjà été effectué.", code="import_already_committed")
    return job


def _table(job: Any) -> tuple[Book, Table]:
    try:
        book = read_workbook(job.filename, job.file_bytes)
        return book, read_table(book, job.sheet, job.header_row)
    except ImportFileError as exc:
        raise _file_error(exc) from None


def _describe(job_id: uuid.UUID, filename: str, book: Book, sheet: str, header_row: int, table: Table) -> ImportOut:
    return ImportOut(
        id=job_id,
        filename=filename,
        sheets=book.sheet_names,
        sheet=sheet,
        header_row=header_row,
        columns=[ColumnOut(index=i, header=h, samples=samples(table, i)) for i, h in enumerate(table.headers)],
        row_count=len(table.rows),
        suggested_mapping=suggest_mapping(table.headers) if header_row else suggest_mapping([]),
    )


def delete_expired_imports(conn: Connection, now: datetime) -> int:
    """Uploaded files (and the reports of committed imports) live 24 h at most."""
    return conn.execute(delete(import_job).where(import_job.c.expires_at < now)).rowcount or 0


def cleanup_imports(ctx: AppContext) -> None:
    with ctx.engine.begin() as conn:
        delete_expired_imports(conn, ctx.clock.now())


# --- mapping ---------------------------------------------------------------------------------------------------

def check_mapping(kind: str, mapping: dict[str, int | None], width: int) -> dict[str, int]:
    allowed = FIELDS_BY_KIND[kind]
    for name in mapping:
        if name not in allowed:
            raise unprocessable(f"Champ inconnu pour cet import : {name}.", code="unknown_field")
    for index in mapping.values():
        if index is not None and not 0 <= index < width:
            raise unprocessable("Colonne inexistante.", code="invalid_column")
    used = {name: index for name, index in mapping.items() if index is not None}
    missing = []
    if not ("fullName" in used or ("lastName" in used and "firstName" in used)):
        missing.append("nom et prénom")
    if kind == "patients" and "phone" not in used:
        missing.append("téléphone")
    if kind == "appointments" and not ("datetime" in used or ("date" in used and "time" in used)):
        missing.append("date et heure")
    if missing:
        raise unprocessable("Champs obligatoires manquants : " + ", ".join(missing) + ".", code="missing_required_field")
    return used


# --- one row ---------------------------------------------------------------------------------------------------

@dataclass
class Row:
    number: int
    cells: list[Any]
    used: dict[str, int]
    problems: list[RowProblem] = field(default_factory=list)

    def get(self, name: str) -> Any:
        index = self.used.get(name)
        return None if index is None else self.cells[index]

    def fail(self, name: str, message: str) -> None:
        self.problems.append(RowProblem(row=self.number, field=name, message=message, value=as_text(self.get(name))))

    def parse(self, name: str, parser: Callable[[Any], Any]) -> Any:
        try:
            return parser(self.get(name))
        except ImportValueError as exc:
            self.fail(name, str(exc))
            return None

    def free_text(self, name: str, limit: int) -> str:
        raw = self.get(name)
        text = raw.strip() if isinstance(raw, str) else as_text(raw)
        if len(text) > limit:
            self.fail(name, f"Texte trop long ({limit} caractères au maximum).")
        return text

    def names(self, order: NameOrder) -> tuple[str, str]:
        if "fullName" in self.used and not ("lastName" in self.used and "firstName" in self.used):
            full = clean_name(self.get("fullName"))
            if not full:
                self.fail("fullName", "Nom complet manquant.")
                return "", ""
            try:
                first, last = split_full_name(full, order)
            except ImportValueError as exc:
                self.fail("fullName", str(exc))
                return "", ""
            source_first = source_last = "fullName"
        else:
            last, first = clean_name(self.get("lastName")), clean_name(self.get("firstName"))
            source_first, source_last = "firstName", "lastName"
            if not last:
                self.fail("lastName", "Nom manquant.")
            if not first:
                self.fail("firstName", "Prénom manquant.")
        if len(last) > 120:
            self.fail(source_last, "Nom trop long (120 caractères au maximum).")
        if len(first) > 120:
            self.fail(source_first, "Prénom trop long (120 caractères au maximum).")
        return first, last


def person_key(phone: str | None, last: str, first: str) -> tuple[str | None, str, str]:
    return phone, norm(last), norm(first)


@dataclass
class Plan:
    """What a commit would do – the preview shows it, the commit executes it."""

    kind: str
    total: int = 0
    errors: list[RowProblem] = field(default_factory=list)
    error_rows: int = 0
    duplicates: list[Duplicate] = field(default_factory=list)
    conflicts: list[Overlap] = field(default_factory=list)
    skipped_lines: list[dict[str, Any]] = field(default_factory=list)
    #: Report lines of rows that were imported anyway (e.g. an alert that did not fit) – not counted.
    notices: list[dict[str, Any]] = field(default_factory=list)
    creates: list[dict[str, Any]] = field(default_factory=list)  # patients or appointments to insert
    updates: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    new_patients: dict[tuple[str | None, str, str], dict[str, Any]] = field(default_factory=dict)
    sample: list[dict[str, Any]] = field(default_factory=list)

    @property
    def skipped(self) -> int:
        return len(self.skipped_lines)

    def reject(self, row: Row) -> None:
        self.errors.extend(row.problems)
        self.error_rows += 1

    def report_lines(self) -> list[dict[str, Any]]:
        lines = [{"row": p.row, "field": LABELS.get(p.field, p.field), "message": p.message, "value": p.value}
                 for p in self.errors]
        lines += self.skipped_lines + self.notices
        return sorted(lines, key=lambda line: line["row"])


# --- patients --------------------------------------------------------------------------------------------------

def _patient_values(row: Row, options: ImportOptions, today: date) -> dict[str, Any]:
    first, last = row.names(options.name_order)
    phone = row.parse("phone", parse_phone)
    if phone is None and not any(p.field == "phone" for p in row.problems):
        row.fail("phone", "Téléphone manquant.")
    birth_year = None
    if "birthDate" in row.used and not is_blank(row.get("birthDate")):
        born = row.parse("birthDate", lambda v: parse_date(v, options.date_format, today=today))
        if born is not None:
            if 1900 <= born.year and born <= today:
                birth_year = born.year
            else:
                row.fail("birthDate", "Date de naissance invalide.")
    elif "birthYear" in row.used:
        birth_year = row.parse("birthYear", lambda v: parse_year(v, today=today))
    notes = row.free_text("notes", 4800) if "notes" in row.used else ""
    reference = row.free_text("externalRef", 120) if "externalRef" in row.used else ""
    if reference:
        notes = f"{notes}\nRéf. : {reference}" if notes else f"Réf. : {reference}"
    return {
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "birth_year": birth_year,
        "notes": notes,
        "alerts": row.free_text("alerts", MAX_ALERTS) if "alerts" in row.used else "",
        "lang": row.parse("lang", parse_lang),
        "reminder_consent": row.parse("reminderConsent", parse_bool),
        "opening_balance": row.parse("openingBalance", parse_millimes),
    }


def _patient_sample(number: int, v: dict[str, Any], options: ImportOptions) -> dict[str, Any]:
    return {
        "row": number, "firstName": v["first_name"], "lastName": v["last_name"], "phone": v["phone"],
        "birthYear": v["birth_year"], "lang": v["lang"] or options.default_lang,
        "reminderConsent": options.reminder_consent if v["reminder_consent"] is None else v["reminder_consent"],
        "notes": v["notes"], "alerts": v["alerts"], "openingBalanceMillimes": v["opening_balance"],
    }


def plan_patients(conn: Connection, practice_id: int, table: Table, used: dict[str, int], options: ImportOptions,
                  today: date) -> Plan:
    plan = Plan("patients")
    existing: dict[tuple[str | None, str, str], int] = {}
    alerts_of: dict[int, str] = {}
    for p in conn.execute(select(patient.c.id, patient.c.phone, patient.c.last_name, patient.c.first_name, patient.c.alerts)
                          .where(patient.c.practice_id == practice_id).order_by(patient.c.id)):
        existing.setdefault(person_key(p.phone, p.last_name, p.first_name), p.id)
        alerts_of[p.id] = p.alerts
    seen: set[tuple[str | None, str, str]] = set()
    for number, cells in table.rows:
        plan.total += 1
        row = Row(number, cells, used)
        values = _patient_values(row, options, today)
        if row.problems:
            plan.reject(row)
            continue
        key = person_key(values["phone"], values["last_name"], values["first_name"])
        name = f"{values['first_name']} {values['last_name']}"
        if key in seen:
            plan.duplicates.append(Duplicate(row=number, patient_id=None, name=name))
            if options.duplicates != "create":
                plan.skipped_lines.append({"row": number, "field": LABELS["duplicate"], "value": "",
                                           "message": f"Ligne en double dans le fichier (ignorée) : {name}"})
                continue
        elif key in existing:
            plan.duplicates.append(Duplicate(row=number, patient_id=existing[key], name=name))
            if options.duplicates == "skip":
                plan.skipped_lines.append({"row": number, "field": LABELS["duplicate"], "value": "",
                                           "message": f"Patient déjà présent (ignoré) : {name}"})
                continue
            if options.duplicates == "update":
                seen.add(key)  # a second line of this person: a duplicate in the file (code review M2)
                values = {**values, "alerts": _added_alerts(plan, number, alerts_of[existing[key]], values["alerts"])}
                plan.updates.append((existing[key], values))
                _add_sample(plan, _patient_sample(number, values, options))
                continue
        seen.add(key)
        plan.creates.append(values)
        _add_sample(plan, _patient_sample(number, values, options))
    return plan


def _added_alerts(plan: Plan, number: int, old: str, new: str) -> str:
    """The alerts of an existing patient with ``new`` added (code review M3), or "" when nothing changes: ``new`` is
    empty or already there, or it does not fit – then the report names it, the patient's alerts stay as they are."""
    if not new or new.casefold() in old.casefold():
        return ""
    merged = f"{old}\n{new}" if old else new
    if len(merged) > MAX_ALERTS:
        plan.notices.append({"row": number, "field": LABELS["alerts"], "value": new,
                             "message": f"Alerte médicale non ajoutée : la fiche en contient déjà trop ({MAX_ALERTS} "
                                        "caractères au maximum). À reporter à la main."})
        return ""
    return merged


def _add_sample(plan: Plan, item: dict[str, Any]) -> None:
    if len(plan.sample) < SAMPLE_ROWS:
        plan.sample.append(item)


def _insert_balances(conn: Connection, rows: list[dict[str, Any]]) -> None:
    if rows:
        conn.execute(insert(treatment), rows)


def commit_patients(conn: Connection, practice_id: int, plan: Plan, options: ImportOptions, now: datetime) -> int:
    today = now.astimezone(TUNIS).date()

    def balance(patient_id: int, amount: int) -> dict[str, Any]:
        return {"practice_id": practice_id, "patient_id": patient_id, "label": OPENING_BALANCE, "tooth": None,
                "price_millimes": amount, "performed_on": today, "appointment_id": None, "created_at": now}

    balances = []
    balanced: set[int] = set()  # at most one opening balance per patient and import (code review M2)
    if plan.creates:
        rows = [{
            "practice_id": practice_id, "first_name": v["first_name"], "last_name": v["last_name"], "phone": v["phone"],
            "birth_year": v["birth_year"], "lang": v["lang"] or options.default_lang,
            "reminder_consent": options.reminder_consent if v["reminder_consent"] is None else v["reminder_consent"],
            "notes": v["notes"], "alerts": v["alerts"], "created_at": now,
        } for v in plan.creates]
        ids = [r.id for r in conn.execute(insert(patient).returning(patient.c.id, sort_by_parameter_order=True), rows)]
        balances += [balance(pid, v["opening_balance"]) for pid, v in zip(ids, plan.creates, strict=True)
                     if v["opening_balance"]]
    for patient_id, v in plan.updates:
        current = conn.execute(select(patient.c.notes).where(patient.c.id == patient_id).with_for_update()).one()
        changes: dict[str, Any] = {}
        if v["birth_year"] is not None:
            changes["birth_year"] = v["birth_year"]
        if v["alerts"]:
            changes["alerts"] = v["alerts"]
        if v["lang"] is not None:
            changes["lang"] = v["lang"]
        if v["reminder_consent"] is not None:
            changes["reminder_consent"] = v["reminder_consent"]
        if v["notes"] and v["notes"] not in current.notes:
            changes["notes"] = (f"{current.notes}\n{v['notes']}" if current.notes else v["notes"])[:5000]
        if changes:
            conn.execute(update(patient).where(patient.c.id == patient_id).values(**changes))
        has_balance = conn.execute(
            select(treatment.c.id).where(treatment.c.patient_id == patient_id, treatment.c.label == OPENING_BALANCE)
        ).first()
        if v["opening_balance"] and has_balance is None and patient_id not in balanced:
            balanced.add(patient_id)
            balances.append(balance(patient_id, v["opening_balance"]))
    _insert_balances(conn, balances)
    return len(plan.creates)


# --- appointments ----------------------------------------------------------------------------------------------

def _person_key(text: str) -> str:
    key = norm(text)
    for title in ("docteur", "dr", "pr"):
        if key.startswith(title) and len(key) > len(title) + 2:
            return key[len(title):]
    return key


@dataclass
class Candidate:
    number: int
    values: dict[str, Any]
    patient_id: int | None
    new_key: tuple[str | None, str, str] | None


def plan_appointments(conn: Connection, practice_id: int, table: Table, used: dict[str, int], options: ImportOptions,
                      now: datetime) -> Plan:
    today = now.astimezone(TUNIS).date()
    plan = Plan("appointments")
    p = conn.execute(select(practice.c.default_duration_min).where(practice.c.id == practice_id)).one()
    default_duration = options.default_duration_min or p.default_duration_min
    services: dict[str, Any] = {}
    for s in conn.execute(select(service.c.id, service.c.name_fr, service.c.name_ar, service.c.duration_min)
                          .where(service.c.practice_id == practice_id).order_by(service.c.sort, service.c.id)):
        for name in (s.name_fr, s.name_ar):
            if name:
                services.setdefault(norm(name), s)
    doctors: dict[str, int] = {}
    for d in conn.execute(select(practitioner.c.id, practitioner.c.name, practitioner.c.title)
                          .where(practitioner.c.practice_id == practice_id).order_by(practitioner.c.sort, practitioner.c.id)):
        doctors.setdefault(_person_key(d.name), d.id)
        doctors.setdefault(_person_key(f"{d.title} {d.name}"), d.id)
    by_key: dict[tuple[str | None, str, str], int] = {}
    by_name: dict[tuple[str, str], list[int]] = defaultdict(list)
    for x in conn.execute(select(patient.c.id, patient.c.phone, patient.c.last_name, patient.c.first_name)
                          .where(patient.c.practice_id == practice_id).order_by(patient.c.id)):
        by_key.setdefault(person_key(x.phone, x.last_name, x.first_name), x.id)
        by_name[(norm(x.last_name), norm(x.first_name))].append(x.id)
    new_by_name: dict[tuple[str, str], tuple[str | None, str, str]] = {}

    candidates: list[Candidate] = []
    for number, cells in table.rows:
        plan.total += 1
        row = Row(number, cells, used)
        start = None
        fmt = options.date_format
        # a date-time column that holds only the day takes the time column (code review M5: "RDV" + "Heure")
        day_column = "datetime" if "datetime" in used and not is_blank(row.get("datetime")) else "date"
        if day_column == "datetime" and not ("time" in used and is_date_only(row.get("datetime"), fmt, today=today)):
            start = row.parse("datetime", lambda v: parse_datetime(v, fmt, today=today, nearest_century=True))
        elif day_column in used and "time" in used:
            day = row.parse(day_column, lambda v: parse_date(v, fmt, today=today, nearest_century=True))
            moment = row.parse("time", parse_time)
            if day is None and not any(x.field == day_column for x in row.problems):
                row.fail(day_column, "Date manquante.")
            if moment is None and not any(x.field == "time" for x in row.problems):
                row.fail("time", "Heure manquante.")
            if day is not None and moment is not None:
                start = datetime.combine(day, moment)
        else:
            row.fail("datetime", "Date et heure manquantes.")
        first, last = row.names(options.name_order)
        phone = row.parse("phone", parse_phone) if "phone" in used else None
        service_text = clean_name(row.get("service")) if "service" in used else ""
        svc = services.get(norm(service_text)) if service_text else None
        doctor_text = clean_name(row.get("practitioner")) if "practitioner" in used else ""
        doctor_id = doctors.get(_person_key(doctor_text)) if doctor_text else None
        if doctor_text and doctor_id is None:
            row.fail("practitioner", "Praticien inconnu.")
        duration = row.parse("durationMin", parse_duration) if "durationMin" in used else None
        if duration is None and "endTime" in used and start is not None and not is_blank(row.get("endTime")):
            end = row.parse("endTime", parse_time)
            if end is not None:
                minutes = int((datetime.combine(start.date(), end) - start).total_seconds() // 60)
                if not 5 <= minutes <= 480:
                    row.fail("endTime", "Heure de fin invalide.")
                else:
                    duration = minutes
        duration = duration or (svc.duration_min if svc else default_duration)
        notes = row.free_text("notes", 2000) if "notes" in used else ""
        patient_id, new_key = None, None
        if not row.problems:
            name_key = (norm(last), norm(first))
            if phone:
                key = person_key(phone, last, first)
                patient_id = by_key.get(key)
                if patient_id is None:
                    new_key = key
                    new_by_name.setdefault(name_key, key)
                    plan.new_patients.setdefault(key, {"first_name": first, "last_name": last, "phone": phone})
            elif len(by_name.get(name_key, [])) == 1:
                patient_id = by_name[name_key][0]
            elif len(by_name.get(name_key, [])) > 1:
                row.fail("phone", "Plusieurs patients portent ce nom : indiquez le téléphone.")
            elif name_key in new_by_name:
                new_key = new_by_name[name_key]
            else:
                row.fail("phone", "Téléphone requis pour créer le patient.")
        if row.problems:
            plan.reject(row)
            continue
        starts_at = start.replace(tzinfo=TUNIS)
        candidates.append(Candidate(number, {
            "practitioner_id": doctor_id,
            "service_id": svc.id if svc else None,
            "starts_at": starts_at,
            "duration_min": duration,
            "ends_at": starts_at + timedelta(minutes=duration),
            "reason": (svc.name_fr if svc else service_text)[:300],
            "status": "done" if starts_at < now else "scheduled",
            "notes": notes,
            "first_name": first, "last_name": last, "phone": phone,
        }, patient_id, new_key))

    _drop_overlaps(conn, practice_id, plan, candidates, active_practitioners(conn, practice_id))
    referenced = {c.new_key for c in candidates if c.new_key is not None and c.values.get("accepted")}
    plan.new_patients = {k: v for k, v in plan.new_patients.items() if k in referenced}
    return plan


def _days(start: datetime, end: datetime) -> list[date]:
    first, last = start.astimezone(TUNIS).date(), (end - timedelta(microseconds=1)).astimezone(TUNIS).date()
    return [first + timedelta(days=n) for n in range((last - first).days + 1)]


def _drop_overlaps(conn: Connection, practice_id: int, plan: Plan, candidates: list[Candidate], doctors: list[int]) -> None:
    """Keeps the file order: a row that overlaps an existing appointment or an earlier row is listed, not imported.
    A row without practitioner takes the first of the active ``doctors`` free at its time (code review H1)."""
    busy: dict[tuple[Any, ...], list[tuple[datetime, datetime]]] = defaultdict(list)

    def book(keys: list[tuple[Any, ...]], start: datetime, end: datetime) -> None:
        for key in keys:
            for day in _days(start, end):
                busy[(*key, day)].append((start, end))

    def free(keys: list[tuple[Any, ...]], start: datetime, end: datetime) -> bool:
        return all(not (s < end and start < e) for key in keys for day in _days(start, end) for s, e in busy[(*key, day)])

    if candidates:
        low = min(c.values["starts_at"] for c in candidates)
        high = max(c.values["ends_at"] for c in candidates)
        for a in conn.execute(
            select(appointment.c.practitioner_id, appointment.c.patient_id, appointment.c.starts_at, appointment.c.ends_at)
            .where(appointment.c.practice_id == practice_id, appointment.c.status.not_in(FREEING_STATUSES),
                   appointment.c.starts_at < high, appointment.c.ends_at > low)
        ):
            book([("lane", a.practitioner_id or 0), ("patient", a.patient_id)], a.starts_at, a.ends_at)
    for c in candidates:
        who = ("patient", c.patient_id) if c.patient_id is not None else ("new", c.new_key)
        start, end = c.values["starts_at"], c.values["ends_at"]
        if c.values["practitioner_id"] is None and doctors:
            c.values["practitioner_id"] = next((d for d in doctors if free([("lane", d)], start, end)), doctors[0])
        keys = [("lane", c.values["practitioner_id"] or 0), who]
        if not free(keys, start, end):
            plan.conflicts.append(Overlap(row=c.number, starts_at=start, message="Chevauchement avec un autre rendez-vous."))
            plan.skipped_lines.append({"row": c.number, "field": LABELS["overlap"], "value": as_text(start.astimezone(TUNIS).replace(tzinfo=None)),
                                       "message": "Chevauchement avec un autre rendez-vous."})
            continue
        book(keys, start, end)
        c.values["accepted"] = True
        plan.creates.append({**c.values, "patient_id": c.patient_id, "new_key": c.new_key, "row": c.number})
        _add_sample(plan, {
            "row": c.number, "startsAt": start.astimezone(TUNIS).isoformat(timespec="seconds"),
            "durationMin": c.values["duration_min"], "firstName": c.values["first_name"],
            "lastName": c.values["last_name"], "phone": c.values["phone"], "patientId": c.patient_id,
            "serviceId": c.values["service_id"], "practitionerId": c.values["practitioner_id"],
            "status": c.values["status"], "notes": c.values["notes"],
        })


def commit_appointments(conn: Connection, user: Principal, plan: Plan, options: ImportOptions, now: datetime) -> int:
    ids: dict[tuple[str | None, str, str], int] = {}
    if plan.new_patients:
        keys = list(plan.new_patients)
        rows = [{"practice_id": user.pid, **plan.new_patients[k], "lang": options.default_lang,
                 "reminder_consent": options.reminder_consent, "created_at": now} for k in keys]
        result = conn.execute(insert(patient).returning(patient.c.id, sort_by_parameter_order=True), rows)
        ids = {k: r.id for k, r in zip(keys, result, strict=True)}
    rows = [{
        "practice_id": user.pid, "patient_id": c["patient_id"] if c["patient_id"] is not None else ids[c["new_key"]],
        "practitioner_id": c["practitioner_id"], "service_id": c["service_id"], "starts_at": c["starts_at"],
        "duration_min": c["duration_min"], "ends_at": c["ends_at"], "reason": c["reason"], "status": c["status"],
        "source": "staff", "notes": c["notes"], "created_by": user.user_id, "created_at": now,
    } for c in plan.creates]
    if rows:
        try:
            with conn.begin_nested():
                conn.execute(insert(appointment), rows)
        except IntegrityError as exc:
            if constraint_name(exc) in (PRACTITIONER_OVERLAP, PATIENT_OVERLAP):
                raise conflict("Un rendez-vous a été ajouté entre-temps. Relancez l'aperçu.", code="import_conflict") from None
            raise
    return len(plan.new_patients)


# --- endpoints -------------------------------------------------------------------------------------------------

def _plan(conn: Connection, user: Principal, job: Any, body: MappingIn, now: datetime) -> Plan:
    _, table = _table(job)
    used = check_mapping(body.kind, body.mapping, len(table.headers))
    if body.kind == "patients":
        return plan_patients(conn, user.pid, table, used, body.options, now.astimezone(TUNIS).date())
    return plan_appointments(conn, user.pid, table, used, body.options, now)


def _make_room(conn: Connection, practice_id: int) -> None:
    """Deletes the oldest open jobs of the practice so that the next one is the ``MAX_OPEN_JOBS``-th."""
    is_open = (import_job.c.practice_id == practice_id) & import_job.c.committed_at.is_(None)
    newest = (select(import_job.c.id).where(is_open)
              .order_by(import_job.c.created_at.desc(), import_job.c.id.desc()).limit(MAX_OPEN_JOBS - 1))
    conn.execute(delete(import_job).where(is_open, import_job.c.id.not_in(newest)))


@router.post("", status_code=201)
def upload(user: ImportWriter, ctx: Ctx, conn: Conn, file: Annotated[UploadFile, File()]) -> ImportOut:
    if user.is_demo:  # every visitor owns a demo practice: no parsing, no stored files there
        raise forbidden("L'import de fichiers n'est pas disponible dans la démo.", code="demo_import_disabled")
    ctx.limiter("import-upload", UPLOADS_PER_HOUR, timedelta(hours=1)).enforce(
        str(user.user_id), "Trop d'imports en une heure. Veuillez réessayer plus tard.")
    data = file.file.read(MAX_BYTES + 1)
    filename = _clean_filename(file.filename)
    try:
        book = read_workbook(filename, data)
        sheet = next(name for name, rows in book.sheets.items() if any(any(c is not None for c in r) for r in rows))
        table = read_table(book, sheet, 1)
    except ImportFileError as exc:
        raise _file_error(exc) from None
    now = ctx.clock.now()
    _make_room(conn, user.pid)
    job_id = conn.execute(
        insert(import_job)
        .values(practice_id=user.pid, created_by=user.user_id, filename=filename, file_bytes=data, created_at=now,
                expires_at=now + JOB_TTL, sheet=sheet, header_row=1)
        .returning(import_job.c.id)
    ).scalar_one()
    return _describe(job_id, filename, book, sheet, 1, table)


@router.post("/{job_id}/sheet")
def choose_sheet(job_id: uuid.UUID, body: SheetIn, user: ImportWriter, ctx: Ctx, conn: Conn) -> ImportOut:
    job = _open_job(conn, user, job_id, ctx.clock.now())
    try:
        book = read_workbook(job.filename, job.file_bytes)
        table = read_table(book, body.sheet, body.header_row)
    except ImportFileError as exc:
        raise _file_error(exc) from None
    conn.execute(update(import_job).where(import_job.c.id == job.id).values(sheet=body.sheet, header_row=body.header_row))
    return _describe(job.id, job.filename, book, body.sheet, body.header_row, table)


@router.post("/{job_id}/preview")
def preview(job_id: uuid.UUID, body: MappingIn, user: ImportWriter, ctx: Ctx, conn: Conn) -> PreviewOut:
    now = ctx.clock.now()
    plan = _plan(conn, user, _open_job(conn, user, job_id, now), body, now)
    return PreviewOut(
        will_create=len(plan.creates),
        will_update=len(plan.updates),
        will_skip=plan.skipped,
        will_create_patients=len(plan.new_patients) if plan.kind == "appointments" else len(plan.creates),
        error_count=plan.error_rows,
        errors=plan.errors[:LIST_LIMIT],
        duplicates=plan.duplicates[:LIST_LIMIT],
        conflicts=plan.conflicts[:LIST_LIMIT],
        sample=plan.sample,
    )


@router.post("/{job_id}/commit")
def commit(job_id: uuid.UUID, body: MappingIn, user: ImportWriter, ctx: Ctx, conn: Conn) -> CommitOut:
    now = ctx.clock.now()
    job = _open_job(conn, user, job_id, now)
    plan = _plan(conn, user, job, body, now)
    if plan.kind == "patients":
        patients_created = commit_patients(conn, user.pid, plan, body.options, now)
    else:
        patients_created = commit_appointments(conn, user, plan, body.options, now)
    conn.execute(
        update(import_job)
        .where(import_job.c.id == job.id)
        .values(committed_at=now, file_bytes=None, report={"kind": plan.kind, "lines": plan.report_lines()})
    )
    conn.execute(update(practice).where(practice.c.id == user.pid).values(onboarding=flag("import")))  # "Erste Schritte"
    if plan.kind == "appointments" and plan.creates:
        ctx.metrics.appointments_created.labels("import").inc(len(plan.creates))
    return CommitOut(created=len(plan.creates), updated=len(plan.updates), skipped=plan.skipped,
                     error_count=plan.error_rows, patients_created=patients_created)


_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def defuse(cell: str) -> str:
    """CSV injection: a cell that a spreadsheet would run as a formula gets a leading apostrophe."""
    return "'" + cell if cell.startswith(_FORMULA_START) else cell


@router.get("/{job_id}/report.csv")
def report(job_id: uuid.UUID, user: ImportReader, ctx: Ctx, conn: Conn) -> Response:
    job = _job(conn, user, job_id, ctx.clock.now())
    if job.committed_at is None or job.report is None:
        raise conflict("Le rapport est disponible après l'import.", code="import_not_committed")
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Ligne", "Champ", "Message", "Valeur"])
    for line in job.report["lines"]:
        writer.writerow([defuse(str(line["row"])), defuse(line["field"]), defuse(line["message"]), defuse(line["value"])])
    name = f"rapport-import-{today_tunis(ctx.clock).isoformat()}.csv"
    return Response(
        ("﻿" + out.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


# --- templates -------------------------------------------------------------------------------------------------

def _check_template_mapping(kind: str, mapping: dict[str, int | None]) -> None:
    for name, index in mapping.items():
        if name not in FIELDS_BY_KIND[kind]:
            raise unprocessable(f"Champ inconnu pour cet import : {name}.", code="unknown_field")
        if index is not None and not 0 <= index < MAX_COLUMNS:
            raise unprocessable("Colonne inexistante.", code="invalid_column")


def _template_out(row: Any) -> TemplateOut:
    return TemplateOut(id=row.id, name=row.name, kind=row.kind, mapping=row.mapping,
                       options=ImportOptions.model_validate(row.options), created_at=row.created_at)


@template_router.get("")
def list_templates(user: ImportReader, conn: Conn) -> list[TemplateOut]:
    rows = conn.execute(select(import_template).where(import_template.c.practice_id == user.pid)
                        .order_by(import_template.c.created_at.desc(), import_template.c.id.desc()))
    return [_template_out(r) for r in rows]


@template_router.post("", status_code=201)
def create_template(body: TemplateIn, user: ImportWriter, ctx: Ctx, conn: Conn) -> TemplateOut:
    _check_template_mapping(body.kind, body.mapping)
    count = conn.execute(select(func.count()).select_from(import_template)
                         .where(import_template.c.practice_id == user.pid)).scalar_one()
    if count >= MAX_TEMPLATES:
        raise unprocessable("Trop de modèles enregistrés.", code="too_many_templates")
    row = conn.execute(
        insert(import_template)
        .values(practice_id=user.pid, name=body.name, kind=body.kind, mapping=body.mapping,
                options=body.options.model_dump(by_alias=True), created_at=ctx.clock.now())
        .returning(import_template)
    ).one()
    return _template_out(row)


@template_router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, user: ImportWriter, conn: Conn) -> Response:
    result = conn.execute(delete(import_template).where(import_template.c.id == template_id,
                                                        import_template.c.practice_id == user.pid))
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)
