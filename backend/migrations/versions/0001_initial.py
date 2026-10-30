"""Initial schema: every table of the design (sections 4, 11–14, backlog) with constraints, indexes, cascades.

Revision ID: 0001
Revises:
Create Date: 2026-10-30

Conventions
- ids are BIGINT identity columns; instants TIMESTAMPTZ; days DATE; money BIGINT millimes (never floats).
- every business table has practice_id → practice ON DELETE CASCADE (deleting a practice deletes everything).
- references to patient are composite (patient_id, practice_id), so no row can point into another practice.
- free text is NOT NULL DEFAULT '' (no NULL/'' ambiguity); optional structured values are NULL.
- public tokens (display_token, ticket_token) default to 32 random hex characters; secrets (invitation and booking
  tokens) are never stored, only their SHA-256 (64 hex characters).
- no double bookings (section 11.1): two EXCLUDE constraints (btree_gist) on appointment – one practitioner (or
  "no practitioner") and one patient are never booked twice at the same time; cancelled and no-show appointments
  free their slot. Constraint names are stable: the API maps them to 409 (see daftar/db.py constraint_name).
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

RANDOM_TOKEN = "replace(gen_random_uuid()::text, '-', '')"
E164 = "'^\\+[1-9][0-9]{7,14}$'"
COLOR = "'^#[0-9a-f]{6}$'"
SHA256 = "'^[0-9a-f]{64}$'"
SPECIALTIES = (
    "'generaliste', 'dentiste', 'pediatre', 'gynecologue', 'dermatologue', 'ophtalmologue', "
    "'cardiologue', 'orl', 'kinesitherapeute', 'psychologue', 'autre'"
)
GOVERNORATES = (
    "'ariana', 'beja', 'ben_arous', 'bizerte', 'gabes', 'gafsa', 'jendouba', 'kairouan', 'kasserine', 'kebili', "
    "'kef', 'mahdia', 'manouba', 'medenine', 'monastir', 'nabeul', 'sfax', 'sidi_bouzid', 'siliana', 'sousse', "
    "'tataouine', 'tozeur', 'tunis', 'zaghouan'"
)
RESERVED_SLUGS = (
    "'www', 'app', 'api', 'admin', 'demo', 'mail', 'smtp', 'static', 'assets', 'daftar', 'status', 'monitoring', 'test'"
)
WEEKLY_HOURS = (
    '{"1": [["08:00", "12:30"], ["14:00", "18:00"]], "2": [["08:00", "12:30"], ["14:00", "18:00"]], '
    '"3": [["08:00", "12:30"], ["14:00", "18:00"]], "4": [["08:00", "12:30"], ["14:00", "18:00"]], '
    '"5": [["08:00", "12:30"], ["14:00", "18:00"]], "6": [["08:00", "12:30"], ["14:00", "18:00"]], "7": []}'
)
REMINDER_FR = (
    "Bonjour {patient}, nous vous rappelons votre rendez-vous le {date} à {time} au {practice}. "
    "En cas d''empêchement, merci de nous prévenir au {phone}."
)
REMINDER_AR = (
    "مرحبا {patient}، نذكّركم بموعدكم يوم {date} على الساعة {time} في {practice}. "
    "في حال تعذّر الحضور، يرجى إعلامنا على الرقم {phone}."
)
FREE = "status NOT IN ('cancelled', 'no_show')"

UPGRADE = f"""
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE plan (
    code            TEXT    PRIMARY KEY CHECK (code ~ '^[a-z0-9_]{{2,40}}$'),
    name_fr         TEXT    NOT NULL CHECK (char_length(name_fr) BETWEEN 1 AND 120),
    name_ar         TEXT    NOT NULL DEFAULT '' CHECK (char_length(name_ar) <= 120),
    price_millimes  BIGINT  NOT NULL CHECK (price_millimes >= 0),
    period_months   INTEGER NOT NULL CHECK (period_months BETWEEN 1 AND 24),
    active          BOOLEAN NOT NULL DEFAULT true
);
INSERT INTO plan (code, name_fr, name_ar, price_millimes, period_months) VALUES
    ('pilot', 'Phase pilote', 'المرحلة التجريبية', 0, 1),
    ('cabinet_mensuel', 'Cabinet – mensuel', 'العيادة – شهري', 49000, 1),
    ('cabinet_annuel', 'Cabinet – annuel', 'العيادة – سنوي', 490000, 12);

CREATE TABLE practice (
    id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                      TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    name_ar                   TEXT        NOT NULL DEFAULT '' CHECK (char_length(name_ar) <= 120),
    slug                      TEXT        NOT NULL,
    specialty                 TEXT        NOT NULL,
    contact_name              TEXT        NOT NULL DEFAULT '' CHECK (char_length(contact_name) <= 120),
    address                   TEXT        NOT NULL DEFAULT '' CHECK (char_length(address) <= 300),
    postal_code               TEXT        NOT NULL DEFAULT '' CHECK (char_length(postal_code) <= 10),
    city                      TEXT        NOT NULL DEFAULT '' CHECK (char_length(city) <= 120),
    governorate               TEXT        NULL CHECK (governorate IN ({GOVERNORATES})),
    phone                     TEXT        NOT NULL DEFAULT '' CHECK (char_length(phone) <= 40),
    whatsapp                  TEXT        NULL CHECK (whatsapp ~ {E164}),
    email                     TEXT        NULL CHECK (char_length(email) <= 254),
    maps_url                  TEXT        NOT NULL DEFAULT '' CHECK (char_length(maps_url) <= 500),
    description_fr            TEXT        NOT NULL DEFAULT '' CHECK (char_length(description_fr) <= 2000),
    description_ar            TEXT        NOT NULL DEFAULT '' CHECK (char_length(description_ar) <= 2000),
    tax_id                    TEXT        NOT NULL DEFAULT '' CHECK (char_length(tax_id) <= 40),
    brand_color               TEXT        NOT NULL DEFAULT '#0f766e',
    weekly_hours              JSONB       NOT NULL DEFAULT '{WEEKLY_HOURS}'::jsonb,
    slot_minutes              INTEGER     NOT NULL DEFAULT 15 CHECK (slot_minutes IN (5, 10, 15, 20, 30, 60)),
    default_duration_min      INTEGER     NOT NULL DEFAULT 30 CHECK (default_duration_min BETWEEN 5 AND 480),
    reminder_template_fr      TEXT        NOT NULL DEFAULT '{REMINDER_FR}' CHECK (char_length(reminder_template_fr) <= 1000),
    reminder_template_ar      TEXT        NOT NULL DEFAULT '{REMINDER_AR}' CHECK (char_length(reminder_template_ar) <= 1000),
    display_token             TEXT        NOT NULL DEFAULT {RANDOM_TOKEN},
    is_demo                   BOOLEAN     NOT NULL DEFAULT false,
    demo_expires_at           TIMESTAMPTZ NULL,
    plan_code                 TEXT        NOT NULL DEFAULT 'pilot' REFERENCES plan (code),
    status                    TEXT        NOT NULL DEFAULT 'pilot' CHECK (status IN
                                  ('pilot', 'trial', 'active', 'past_due', 'suspended', 'canceled')),
    paid_until                DATE        NULL,
    admin_notes               TEXT        NOT NULL DEFAULT '' CHECK (char_length(admin_notes) <= 5000),
    online_booking_enabled    BOOLEAN     NOT NULL DEFAULT false,
    online_auto_confirm       BOOLEAN     NOT NULL DEFAULT false,
    booking_horizon_days      INTEGER     NOT NULL DEFAULT 30 CHECK (booking_horizon_days BETWEEN 1 AND 365),
    booking_min_notice_hours  INTEGER     NOT NULL DEFAULT 2 CHECK (booking_min_notice_hours BETWEEN 0 AND 168),
    booking_max_per_day       INTEGER     NOT NULL DEFAULT 20 CHECK (booking_max_per_day BETWEEN 1 AND 500),
    booking_block_no_shows    INTEGER     NOT NULL DEFAULT 2 CHECK (booking_block_no_shows BETWEEN 0 AND 20),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT practice_slug_key UNIQUE (slug),
    CONSTRAINT practice_slug_format CHECK (slug ~ '^[a-z0-9](?:[a-z0-9-]{{1,38}}[a-z0-9])$'),
    CONSTRAINT practice_slug_reserved CHECK (slug NOT IN ({RESERVED_SLUGS})),
    CONSTRAINT practice_specialty_check CHECK (specialty IN ({SPECIALTIES})),
    CONSTRAINT practice_brand_color_check CHECK (brand_color ~ {COLOR}),
    CONSTRAINT practice_weekly_hours_check CHECK (jsonb_typeof(weekly_hours) = 'object'),
    CONSTRAINT practice_display_token_key UNIQUE (display_token),
    CONSTRAINT practice_demo_check CHECK (NOT is_demo OR demo_expires_at IS NOT NULL)
);
CREATE INDEX practice_demo_expires_idx ON practice (demo_expires_at) WHERE is_demo;

CREATE TABLE app_user (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email          TEXT        NOT NULL CHECK (email = lower(email) AND char_length(email) BETWEEN 3 AND 254),
    password_hash  TEXT        NOT NULL,
    token_version  INTEGER     NOT NULL DEFAULT 0,
    practice_id    BIGINT      NULL REFERENCES practice (id) ON DELETE CASCADE,
    role           TEXT        NOT NULL CHECK (role IN ('admin', 'owner', 'dentist', 'assistant')),
    name           TEXT        NOT NULL DEFAULT '' CHECK (char_length(name) <= 120),
    lang           TEXT        NOT NULL DEFAULT 'fr' CHECK (lang IN ('fr', 'ar')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT app_user_email_key UNIQUE (email),
    -- the admin has no practice, everybody else exactly one
    CONSTRAINT app_user_practice_check CHECK ((role = 'admin') = (practice_id IS NULL))
);
CREATE INDEX app_user_practice_idx ON app_user (practice_id);

CREATE TABLE practitioner (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name            TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    title           TEXT        NOT NULL DEFAULT 'Dr.' CHECK (char_length(title) <= 20),
    specialty       TEXT        NULL CHECK (specialty IN ({SPECIALTIES})),
    color           TEXT        NOT NULL DEFAULT '#0f766e' CHECK (color ~ {COLOR}),
    user_id         BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    online_bookable BOOLEAN     NOT NULL DEFAULT true,
    active          BOOLEAN     NOT NULL DEFAULT true,
    sort            INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX practitioner_practice_idx ON practitioner (practice_id, sort);
CREATE INDEX practitioner_user_idx ON practitioner (user_id);

CREATE TABLE service (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name_fr         TEXT        NOT NULL CHECK (char_length(name_fr) BETWEEN 1 AND 120),
    name_ar         TEXT        NOT NULL DEFAULT '' CHECK (char_length(name_ar) <= 120),
    duration_min    INTEGER     NOT NULL CHECK (duration_min BETWEEN 5 AND 480),
    price_millimes  BIGINT      NULL CHECK (price_millimes >= 0),
    online_bookable BOOLEAN     NOT NULL DEFAULT false,
    color           TEXT        NULL CHECK (color ~ {COLOR}),
    active          BOOLEAN     NOT NULL DEFAULT true,
    sort            INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX service_practice_idx ON service (practice_id, sort);

CREATE TABLE practice_closure (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    starts_on    DATE        NOT NULL,
    ends_on      DATE        NOT NULL,
    label        TEXT        NOT NULL DEFAULT '' CHECK (char_length(label) <= 120),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT practice_closure_dates_check CHECK (ends_on >= starts_on)
);
CREATE INDEX practice_closure_practice_idx ON practice_closure (practice_id, starts_on);

CREATE TABLE invitation (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    role         TEXT        NOT NULL CHECK (role IN ('owner', 'dentist', 'assistant')),
    token_hash   TEXT        NOT NULL CHECK (token_hash ~ {SHA256}),
    created_by   BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    used_at      TIMESTAMPTZ NULL,
    CONSTRAINT invitation_token_hash_key UNIQUE (token_hash)
);
CREATE INDEX invitation_practice_idx ON invitation (practice_id);
CREATE INDEX invitation_created_by_idx ON invitation (created_by);

CREATE TABLE patient (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id       BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    first_name        TEXT        NOT NULL CHECK (char_length(first_name) BETWEEN 1 AND 120),
    last_name         TEXT        NOT NULL CHECK (char_length(last_name) BETWEEN 1 AND 120),
    phone             TEXT        NOT NULL CHECK (phone ~ {E164}),
    birth_year        INTEGER     NULL CHECK (birth_year BETWEEN 1900 AND 2100),
    lang              TEXT        NOT NULL DEFAULT 'fr' CHECK (lang IN ('fr', 'ar')),
    reminder_consent  BOOLEAN     NOT NULL DEFAULT false,
    notes             TEXT        NOT NULL DEFAULT '' CHECK (char_length(notes) <= 5000),
    alerts            TEXT        NOT NULL DEFAULT '' CHECK (char_length(alerts) <= 1000),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT patient_id_practice_key UNIQUE (id, practice_id)
);
CREATE INDEX patient_name_idx ON patient (practice_id, last_name, first_name);
CREATE INDEX patient_phone_idx ON patient (practice_id, phone);

CREATE TABLE appointment (
    id                         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id                BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    patient_id                 BIGINT      NOT NULL,
    practitioner_id            BIGINT      NULL REFERENCES practitioner (id) ON DELETE SET NULL,
    service_id                 BIGINT      NULL REFERENCES service (id) ON DELETE SET NULL,
    starts_at                  TIMESTAMPTZ NOT NULL,
    duration_min               INTEGER     NOT NULL DEFAULT 30 CHECK (duration_min BETWEEN 5 AND 480),
    ends_at                    TIMESTAMPTZ NOT NULL,
    reason                     TEXT        NOT NULL DEFAULT '' CHECK (char_length(reason) <= 300),
    status                     TEXT        NOT NULL DEFAULT 'scheduled' CHECK (status IN ('requested', 'scheduled',
                                   'confirmed', 'arrived', 'in_treatment', 'done', 'no_show', 'cancelled')),
    source                     TEXT        NOT NULL DEFAULT 'staff' CHECK (source IN ('staff', 'online')),
    notes                      TEXT        NOT NULL DEFAULT '' CHECK (char_length(notes) <= 2000),
    patient_note               TEXT        NOT NULL DEFAULT '' CHECK (char_length(patient_note) <= 1000),
    deposit_required_millimes  BIGINT      NOT NULL DEFAULT 0 CHECK (deposit_required_millimes >= 0),
    reminder_sent_at           TIMESTAMPTZ NULL,
    booking_token_hash         TEXT        NULL CHECK (booking_token_hash ~ {SHA256}),
    series_id                  UUID        NULL,
    created_by                 BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT appointment_ends_check CHECK (ends_at > starts_at),
    CONSTRAINT appointment_duration_check CHECK (ends_at = starts_at + duration_min * interval '1 minute'),
    CONSTRAINT appointment_booking_token_hash_key UNIQUE (booking_token_hash),
    CONSTRAINT appointment_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE,
    CONSTRAINT appointment_practitioner_no_overlap EXCLUDE USING gist (
        practice_id WITH =, (coalesce(practitioner_id, 0)) WITH =, tstzrange(starts_at, ends_at) WITH &&
    ) WHERE ({FREE}),
    CONSTRAINT appointment_patient_no_overlap EXCLUDE USING gist (
        practice_id WITH =, patient_id WITH =, tstzrange(starts_at, ends_at) WITH &&
    ) WHERE ({FREE})
);
CREATE INDEX appointment_practice_starts_idx ON appointment (practice_id, starts_at);
CREATE INDEX appointment_patient_idx ON appointment (patient_id, starts_at DESC);
CREATE INDEX appointment_practitioner_idx ON appointment (practitioner_id);
CREATE INDEX appointment_service_idx ON appointment (service_id);
CREATE INDEX appointment_created_by_idx ON appointment (created_by);
CREATE INDEX appointment_requested_idx ON appointment (practice_id, starts_at) WHERE status = 'requested';
CREATE INDEX appointment_series_idx ON appointment (series_id) WHERE series_id IS NOT NULL;

CREATE TABLE queue_entry (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    day             DATE        NOT NULL,
    ticket_no       INTEGER     NOT NULL CHECK (ticket_no > 0),
    patient_id      BIGINT      NULL,
    appointment_id  BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    name            TEXT        NOT NULL DEFAULT '' CHECK (char_length(name) <= 120),
    phone           TEXT        NULL CHECK (phone ~ {E164}),
    status          TEXT        NOT NULL DEFAULT 'waiting' CHECK (status IN ('waiting', 'called', 'in_treatment', 'done', 'left')),
    ticket_token    TEXT        NOT NULL DEFAULT {RANDOM_TOKEN},
    arrived_at      TIMESTAMPTZ NOT NULL,
    called_at       TIMESTAMPTZ NULL,
    done_at         TIMESTAMPTZ NULL,
    CONSTRAINT queue_entry_appointment_id_key UNIQUE (appointment_id),
    CONSTRAINT queue_entry_ticket_token_key UNIQUE (ticket_token),
    CONSTRAINT queue_entry_ticket_key UNIQUE (practice_id, day, ticket_no),
    CONSTRAINT queue_entry_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE
);
CREATE INDEX queue_entry_patient_idx ON queue_entry (patient_id);

CREATE TABLE treatment (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    patient_id      BIGINT      NOT NULL,
    label           TEXT        NOT NULL CHECK (char_length(label) BETWEEN 1 AND 200),
    tooth           TEXT        NULL CHECK (char_length(tooth) <= 20),
    price_millimes  BIGINT      NOT NULL CHECK (price_millimes >= 0),
    performed_on    DATE        NULL,
    appointment_id  BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT treatment_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE
);
CREATE INDEX treatment_patient_idx ON treatment (patient_id);
CREATE INDEX treatment_appointment_idx ON treatment (appointment_id);

CREATE TABLE payment (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id      BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    patient_id       BIGINT      NOT NULL,
    amount_millimes  BIGINT      NOT NULL CHECK (amount_millimes > 0),
    method           TEXT        NOT NULL CHECK (method IN ('cash', 'd17', 'flouci', 'card', 'cheque', 'transfer', 'other')),
    paid_at          TIMESTAMPTZ NOT NULL,
    appointment_id   BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    is_deposit       BOOLEAN     NOT NULL DEFAULT false,
    note             TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    received_by      BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT payment_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE
);
CREATE INDEX payment_practice_paid_idx ON payment (practice_id, paid_at);
CREATE INDEX payment_patient_idx ON payment (patient_id);
CREATE INDEX payment_appointment_idx ON payment (appointment_id);
CREATE INDEX payment_received_by_idx ON payment (received_by);

CREATE TABLE invoice (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id          BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    number               TEXT        NOT NULL CHECK (number ~ '^DAF-[0-9]{{4}}-[0-9]{{4,}}$'),
    plan_code            TEXT        NOT NULL REFERENCES plan (code),
    period_start         DATE        NOT NULL,
    period_end           DATE        NOT NULL,
    amount_millimes      BIGINT      NOT NULL CHECK (amount_millimes >= 0),
    status               TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid', 'void')),
    due_on               DATE        NOT NULL,
    paid_at              TIMESTAMPTZ NULL,
    method               TEXT        NULL CHECK (method IN ('flouci', 'virement', 'especes', 'autre')),
    provider_payment_id  TEXT        NULL CHECK (char_length(provider_payment_id) <= 200),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT invoice_number_key UNIQUE (number),
    CONSTRAINT invoice_period_check CHECK (period_end > period_start),
    CONSTRAINT invoice_paid_check CHECK (status <> 'paid' OR paid_at IS NOT NULL)
);
CREATE INDEX invoice_practice_idx ON invoice (practice_id, period_start DESC);

CREATE TABLE pilot_request (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    practice    TEXT        NOT NULL CHECK (char_length(practice) BETWEEN 1 AND 120),
    city        TEXT        NOT NULL CHECK (char_length(city) BETWEEN 1 AND 120),
    phone       TEXT        NOT NULL CHECK (char_length(phone) BETWEEN 1 AND 40),
    email       TEXT        NULL CHECK (char_length(email) <= 254),
    message     TEXT        NOT NULL DEFAULT '' CHECK (char_length(message) <= 2000),
    lang        TEXT        NOT NULL DEFAULT 'fr' CHECK (lang IN ('fr', 'ar')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pilot_request_created_idx ON pilot_request (created_at DESC);

CREATE TABLE import_job (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    practice_id   BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    created_by    BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    filename      TEXT        NOT NULL CHECK (char_length(filename) BETWEEN 1 AND 255),
    file_bytes    BYTEA       NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    committed_at  TIMESTAMPTZ NULL
);
CREATE INDEX import_job_practice_idx ON import_job (practice_id);
CREATE INDEX import_job_expires_idx ON import_job (expires_at);
CREATE INDEX import_job_created_by_idx ON import_job (created_by);

CREATE TABLE import_template (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name         TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    kind         TEXT        NOT NULL CHECK (kind IN ('patients', 'appointments')),
    mapping      JSONB       NOT NULL,
    options      JSONB       NOT NULL DEFAULT '{{}}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX import_template_practice_idx ON import_template (practice_id);

CREATE TABLE password_reset (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL CHECK (token_hash ~ {SHA256}),
    created_by  BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ NULL,
    CONSTRAINT password_reset_token_hash_key UNIQUE (token_hash)
);
CREATE INDEX password_reset_user_idx ON password_reset (user_id);
CREATE INDEX password_reset_created_by_idx ON password_reset (created_by);

CREATE TABLE feedback (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    user_id      BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    message      TEXT        NOT NULL CHECK (char_length(message) BETWEEN 1 AND 4000),
    page         TEXT        NOT NULL DEFAULT '' CHECK (char_length(page) <= 300),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX feedback_practice_idx ON feedback (practice_id, created_at DESC);
CREATE INDEX feedback_user_idx ON feedback (user_id);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS password_reset;
DROP TABLE IF EXISTS import_template;
DROP TABLE IF EXISTS import_job;
DROP TABLE IF EXISTS pilot_request;
DROP TABLE IF EXISTS invoice;
DROP TABLE IF EXISTS payment;
DROP TABLE IF EXISTS treatment;
DROP TABLE IF EXISTS queue_entry;
DROP TABLE IF EXISTS appointment;
DROP TABLE IF EXISTS patient;
DROP TABLE IF EXISTS invitation;
DROP TABLE IF EXISTS practice_closure;
DROP TABLE IF EXISTS service;
DROP TABLE IF EXISTS practitioner;
DROP TABLE IF EXISTS app_user;
DROP TABLE IF EXISTS practice;
DROP TABLE IF EXISTS plan;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
