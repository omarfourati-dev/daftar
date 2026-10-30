"""SQLAlchemy Core tables – a mirror of the schema created by migrations/versions/0001_initial.py.

Use these for queries (``select(patient).where(patient.c.practice_id == user.pid)``); the migration is the source of
truth for constraints and indexes. tests/test_schema.py checks that both agree (columns, types, nullability).

Tenant rule: every business table has ``practice_id``; every query filters on the practice of the token.
Foreign keys to ``patient`` are composite ``(patient_id, practice_id)``, so a row can never point to a patient of
another practice. Appointments can never overlap for one practitioner (or "no practitioner") or one patient
(EXCLUDE constraints, see :data:`PRACTITIONER_OVERLAP` / :data:`PATIENT_OVERLAP`).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

APPOINTMENT_STATUSES = (
    "requested", "scheduled", "confirmed", "arrived", "in_treatment", "done", "no_show", "cancelled",
)
#: Statuses that free the slot again (every other status blocks it – see the EXCLUDE constraints).
FREEING_STATUSES = ("cancelled", "no_show")
QUEUE_STATUSES = ("waiting", "called", "in_treatment", "done", "left")
PAYMENT_METHODS = ("cash", "d17", "flouci", "card", "cheque", "transfer", "other")
PRACTICE_STATUSES = ("pilot", "trial", "active", "past_due", "suspended", "canceled")
INVOICE_STATUSES = ("open", "paid", "void")
INVOICE_METHODS = ("flouci", "virement", "especes", "autre")
#: Constraint names the API turns into 409 (``daftar.db.constraint_name(exc)``).
PRACTITIONER_OVERLAP = "appointment_practitioner_no_overlap"
PATIENT_OVERLAP = "appointment_patient_no_overlap"


def _id() -> Column:
    return Column("id", BigInteger, primary_key=True, autoincrement=True)


def _ts(name: str, nullable: bool = False) -> Column:
    return Column(name, DateTime(timezone=True), nullable=nullable)


def _practice_id() -> Column:
    return Column("practice_id", BigInteger, ForeignKey("practice.id", ondelete="CASCADE"), nullable=False)


plan = Table(
    "plan",
    metadata,
    Column("code", Text, primary_key=True),
    Column("name_fr", Text, nullable=False),
    Column("name_ar", Text, nullable=False),
    Column("price_millimes", BigInteger, nullable=False),
    Column("period_months", Integer, nullable=False),
    Column("active", Boolean, nullable=False),
)

practice = Table(
    "practice",
    metadata,
    _id(),
    Column("name", Text, nullable=False),
    Column("name_ar", Text, nullable=False),
    Column("slug", Text, nullable=False, unique=True),
    Column("specialty", Text, nullable=False),
    Column("contact_name", Text, nullable=False),
    Column("address", Text, nullable=False),
    Column("postal_code", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("governorate", Text, nullable=True),
    Column("phone", Text, nullable=False),
    Column("whatsapp", Text, nullable=True),
    Column("email", Text, nullable=True),
    Column("maps_url", Text, nullable=False),
    Column("description_fr", Text, nullable=False),
    Column("description_ar", Text, nullable=False),
    Column("tax_id", Text, nullable=False),
    Column("brand_color", Text, nullable=False),
    Column("weekly_hours", JSONB, nullable=False),
    Column("slot_minutes", Integer, nullable=False),
    Column("default_duration_min", Integer, nullable=False),
    Column("reminder_template_fr", Text, nullable=False),
    Column("reminder_template_ar", Text, nullable=False),
    Column("display_token", Text, nullable=False, unique=True),
    Column("is_demo", Boolean, nullable=False),
    _ts("demo_expires_at", nullable=True),
    Column("plan_code", Text, ForeignKey("plan.code"), nullable=False),
    Column("status", Text, nullable=False),
    Column("paid_until", Date, nullable=True),
    Column("admin_notes", Text, nullable=False),
    Column("online_booking_enabled", Boolean, nullable=False),
    Column("online_auto_confirm", Boolean, nullable=False),
    Column("booking_horizon_days", Integer, nullable=False),
    Column("booking_min_notice_hours", Integer, nullable=False),
    Column("booking_max_per_day", Integer, nullable=False),
    Column("booking_block_no_shows", Integer, nullable=False),
    Column("onboarding", JSONB, nullable=False),  # "Erste Schritte" state (migration 0002)
    _ts("created_at"),
)

app_user = Table(
    "app_user",
    metadata,
    _id(),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("token_version", Integer, nullable=False),
    Column("practice_id", BigInteger, ForeignKey("practice.id", ondelete="CASCADE"), nullable=True),
    Column("role", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("lang", Text, nullable=False),
    _ts("created_at"),
)

#: The people who treat patients – not accounts (section 11.2); ``user_id`` optionally links one.
practitioner = Table(
    "practitioner",
    metadata,
    _id(),
    _practice_id(),
    Column("name", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("specialty", Text, nullable=True),
    Column("color", Text, nullable=False),
    Column("user_id", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    Column("online_bookable", Boolean, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("sort", Integer, nullable=False),
    _ts("created_at"),
)

#: The practice's catalog of acts/consultations (default catalogs per specialty: daftar/catalog.py).
service = Table(
    "service",
    metadata,
    _id(),
    _practice_id(),
    Column("name_fr", Text, nullable=False),
    Column("name_ar", Text, nullable=False),
    Column("duration_min", Integer, nullable=False),
    Column("price_millimes", BigInteger, nullable=True),
    Column("online_bookable", Boolean, nullable=False),
    Column("color", Text, nullable=True),
    Column("active", Boolean, nullable=False),
    Column("sort", Integer, nullable=False),
    _ts("created_at"),
)

practice_closure = Table(
    "practice_closure",
    metadata,
    _id(),
    _practice_id(),
    Column("starts_on", Date, nullable=False),
    Column("ends_on", Date, nullable=False),
    Column("label", Text, nullable=False),
    _ts("created_at"),
)

invitation = Table(
    "invitation",
    metadata,
    _id(),
    _practice_id(),
    Column("role", Text, nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("created_by", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    _ts("created_at"),
    _ts("expires_at"),
    _ts("used_at", nullable=True),
)

patient = Table(
    "patient",
    metadata,
    _id(),
    _practice_id(),
    Column("first_name", Text, nullable=False),
    Column("last_name", Text, nullable=False),
    Column("phone", Text, nullable=False),
    Column("birth_year", Integer, nullable=True),
    Column("lang", Text, nullable=False),
    Column("reminder_consent", Boolean, nullable=False),
    Column("notes", Text, nullable=False),
    Column("alerts", Text, nullable=False),  # medical warnings (allergy, anticoagulant) shown in red
    _ts("created_at"),
)

appointment = Table(
    "appointment",
    metadata,
    _id(),
    _practice_id(),
    Column("patient_id", BigInteger, nullable=False),
    Column("practitioner_id", BigInteger, ForeignKey("practitioner.id", ondelete="SET NULL"), nullable=True),
    Column("service_id", BigInteger, ForeignKey("service.id", ondelete="SET NULL"), nullable=True),
    _ts("starts_at"),
    Column("duration_min", Integer, nullable=False),
    _ts("ends_at"),  # always starts_at + duration_min (CHECK) – needed by the no-overlap constraints
    Column("reason", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("notes", Text, nullable=False),
    Column("patient_note", Text, nullable=False),
    Column("deposit_required_millimes", BigInteger, nullable=False),
    _ts("reminder_sent_at", nullable=True),
    Column("booking_token_hash", Text, nullable=True, unique=True),
    Column("series_id", UUID(as_uuid=True), nullable=True),  # recurring appointments share one id
    Column("created_by", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    _ts("created_at"),
)

queue_entry = Table(
    "queue_entry",
    metadata,
    _id(),
    _practice_id(),
    Column("day", Date, nullable=False),
    Column("ticket_no", Integer, nullable=False),
    Column("patient_id", BigInteger, nullable=True),
    Column("appointment_id", BigInteger, ForeignKey("appointment.id", ondelete="SET NULL"), nullable=True, unique=True),
    Column("name", Text, nullable=False),
    Column("phone", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("ticket_token", Text, nullable=False, unique=True),
    _ts("arrived_at"),
    _ts("called_at", nullable=True),
    _ts("done_at", nullable=True),
)

treatment = Table(
    "treatment",
    metadata,
    _id(),
    _practice_id(),
    Column("patient_id", BigInteger, nullable=False),
    Column("label", Text, nullable=False),
    Column("tooth", Text, nullable=True),
    Column("price_millimes", BigInteger, nullable=False),
    Column("performed_on", Date, nullable=True),
    Column("appointment_id", BigInteger, ForeignKey("appointment.id", ondelete="SET NULL"), nullable=True),
    _ts("created_at"),
)

payment = Table(
    "payment",
    metadata,
    _id(),
    _practice_id(),
    Column("patient_id", BigInteger, nullable=False),
    Column("amount_millimes", BigInteger, nullable=False),
    Column("method", Text, nullable=False),
    _ts("paid_at"),
    Column("appointment_id", BigInteger, ForeignKey("appointment.id", ondelete="SET NULL"), nullable=True),
    Column("is_deposit", Boolean, nullable=False),
    Column("note", Text, nullable=False),
    Column("received_by", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    _ts("created_at"),
)

invoice = Table(
    "invoice",
    metadata,
    _id(),
    _practice_id(),
    Column("number", Text, nullable=False, unique=True),
    Column("plan_code", Text, ForeignKey("plan.code"), nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("amount_millimes", BigInteger, nullable=False),
    Column("status", Text, nullable=False),
    Column("due_on", Date, nullable=False),
    _ts("paid_at", nullable=True),
    Column("method", Text, nullable=True),
    Column("provider_payment_id", Text, nullable=True),
    _ts("created_at"),
)

pilot_request = Table(
    "pilot_request",
    metadata,
    _id(),
    Column("name", Text, nullable=False),
    Column("practice", Text, nullable=False),
    Column("city", Text, nullable=False),
    Column("phone", Text, nullable=False),
    Column("email", Text, nullable=True),
    Column("message", Text, nullable=False),
    Column("lang", Text, nullable=False),
    _ts("created_at"),
)

#: Excel/CSV import (section 14): the uploaded file lives here until commit, at most 24 h.
import_job = Table(
    "import_job",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    _practice_id(),
    Column("created_by", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    Column("filename", Text, nullable=False),
    Column("file_bytes", LargeBinary, nullable=True),  # NULL once committed (migration 0003)
    _ts("created_at"),
    _ts("expires_at"),
    _ts("committed_at", nullable=True),
    Column("sheet", Text, nullable=True),  # chosen sheet and header row (migration 0003)
    Column("header_row", Integer, nullable=False),
    Column("report", JSONB, nullable=True),  # problems found by the commit, for report.csv
)

import_template = Table(
    "import_template",
    metadata,
    _id(),
    _practice_id(),
    Column("name", Text, nullable=False),
    Column("kind", Text, nullable=False),  # patients | appointments
    Column("mapping", JSONB, nullable=False),
    Column("options", JSONB, nullable=False),
    _ts("created_at"),
)

#: One-time password reset links (only the SHA-256 of the token is stored).
password_reset = Table(
    "password_reset",
    metadata,
    _id(),
    Column("user_id", BigInteger, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("created_by", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    _ts("created_at"),
    _ts("expires_at"),
    _ts("used_at", nullable=True),
)

feedback = Table(
    "feedback",
    metadata,
    _id(),
    _practice_id(),
    Column("user_id", BigInteger, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    Column("message", Text, nullable=False),
    Column("page", Text, nullable=False),
    _ts("created_at"),
)

#: Child tables first – the order for TRUNCATE/DELETE in tests and tools (reference data not included).
ALL_TABLES = (
    feedback, password_reset, import_template, import_job,
    pilot_request, invoice, payment, treatment, queue_entry, appointment, patient, invitation,
    practice_closure, service, practitioner, app_user, practice,
)
#: Reference data seeded by the migration (plans); tests never empty these.
REFERENCE_TABLES = (plan,)
