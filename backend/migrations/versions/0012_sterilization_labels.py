"""Sterilisation cycles and their labels, traceability of the packs, specimen labels, birth dates
(spec stock-hygiène 5.3, 6, 7).

Additive and safe on the live database – new tables and new nullable / defaulted columns only:

- ``practice.label_settings``: label format per kind (sterile, specimen) and shelf life per packaging (JSON; empty =
  the defaults of :mod:`daftar.label_rules`).
- ``equipment.label_code``: the short code of an autoclave on its labels (``A1``, ``A2`` …), given at its first cycle,
  unique in the practice; ``UNIQUE (id, practice_id)`` so cycles can point to their autoclave within the practice.
- ``sterilization_cycle``: one run of an autoclave – number (unique per autoclave), when, program, result
  ``ok`` / ``not_ok``, number of packs, who ran it (name and initials kept as printed on the labels).
- ``sterile_pack``: one pack of a cycle – its code (unique in the practice), content, packaging, "à utiliser avant".
  The packs go with their cycle; a cycle with a used pack cannot be deleted.
- ``sterile_pack_use``: the pack was opened for this patient (and appointment) – once. It goes with the patient
  (erasure), never with the cycle.
- ``specimen_label_log``: who printed specimen labels for which patient, when, which tubes and how many – no results.
- ``patient.birth_date``: optional; when set, ``birth_year`` is its year (CHECK). Existing patients keep their year.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-01
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

UPGRADE = """
ALTER TABLE practice ADD COLUMN label_settings JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE patient ADD COLUMN birth_date DATE NULL;
ALTER TABLE patient ADD CONSTRAINT patient_birth_date_year_check
    CHECK (birth_date IS NULL OR birth_year IS NOT DISTINCT FROM EXTRACT(YEAR FROM birth_date)::integer);

ALTER TABLE equipment ADD COLUMN label_code TEXT NULL CHECK (label_code ~ '^A[0-9]{1,2}$');
ALTER TABLE equipment ADD CONSTRAINT equipment_id_practice_key UNIQUE (id, practice_id);
CREATE UNIQUE INDEX equipment_label_code_key ON equipment (practice_id, label_code);

CREATE TABLE sterilization_cycle (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id        BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    equipment_id       BIGINT      NOT NULL,
    number             INTEGER     NOT NULL CHECK (number BETWEEN 1 AND 999999),
    run_at             TIMESTAMPTZ NOT NULL,
    program            TEXT        NOT NULL DEFAULT '' CHECK (char_length(program) <= 60),
    result             TEXT        NOT NULL CHECK (result IN ('ok', 'not_ok')),
    pack_count         INTEGER     NOT NULL CHECK (pack_count BETWEEN 0 AND 99),
    note               TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    performed_by       BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    performed_by_name  TEXT        NOT NULL CHECK (char_length(performed_by_name) <= 120),
    initials           TEXT        NOT NULL CHECK (char_length(initials) <= 3),
    created_at         TIMESTAMPTZ NOT NULL,
    CONSTRAINT sterilization_cycle_id_practice_key UNIQUE (id, practice_id),
    -- plain reference, checked at the end of the statement: deleting the whole practice still works
    CONSTRAINT sterilization_cycle_equipment_fkey FOREIGN KEY (equipment_id, practice_id)
        REFERENCES equipment (id, practice_id),
    CONSTRAINT sterilization_cycle_number_key UNIQUE (equipment_id, number)
);
CREATE INDEX sterilization_cycle_practice_idx ON sterilization_cycle (practice_id, run_at DESC);
CREATE INDEX sterilization_cycle_performed_by_idx ON sterilization_cycle (performed_by);

CREATE TABLE sterile_pack (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT  NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    cycle_id     BIGINT  NOT NULL,
    seq          INTEGER NOT NULL CHECK (seq BETWEEN 1 AND 99),
    code         TEXT    NOT NULL CHECK (code ~ '^A[0-9]{1,2}-[0-9]{4,6}-[0-9]{2}$'),
    content      TEXT    NOT NULL CHECK (char_length(content) BETWEEN 1 AND 60),
    packaging    TEXT    NOT NULL CHECK (packaging IN ('sachet', 'double_sachet', 'conteneur', 'champ')),
    expires_on   DATE    NOT NULL,
    CONSTRAINT sterile_pack_id_practice_key UNIQUE (id, practice_id),
    CONSTRAINT sterile_pack_cycle_fkey FOREIGN KEY (cycle_id, practice_id)
        REFERENCES sterilization_cycle (id, practice_id) ON DELETE CASCADE,
    CONSTRAINT sterile_pack_seq_key UNIQUE (cycle_id, seq),
    CONSTRAINT sterile_pack_code_key UNIQUE (practice_id, code)
);
CREATE INDEX sterile_pack_cycle_idx ON sterile_pack (cycle_id);
CREATE INDEX sterile_pack_expires_idx ON sterile_pack (practice_id, expires_on);

CREATE TABLE sterile_pack_use (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    pack_id         BIGINT      NOT NULL,
    patient_id      BIGINT      NOT NULL,
    appointment_id  BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    used_at         TIMESTAMPTZ NOT NULL,
    used_by         BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    used_by_name    TEXT        NOT NULL CHECK (char_length(used_by_name) <= 120),
    CONSTRAINT sterile_pack_use_pack_fkey FOREIGN KEY (pack_id, practice_id) REFERENCES sterile_pack (id, practice_id),
    CONSTRAINT sterile_pack_use_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE,
    CONSTRAINT sterile_pack_use_once UNIQUE (pack_id)
);
CREATE INDEX sterile_pack_use_patient_idx ON sterile_pack_use (patient_id, used_at DESC);
CREATE INDEX sterile_pack_use_appointment_idx ON sterile_pack_use (appointment_id);
CREATE INDEX sterile_pack_use_used_by_idx ON sterile_pack_use (used_by);

CREATE TABLE specimen_label_log (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id      BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    patient_id       BIGINT      NOT NULL,
    appointment_id   BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    items            JSONB       NOT NULL,
    label_count      INTEGER     NOT NULL CHECK (label_count BETWEEN 1 AND 48),
    collected_at     TIMESTAMPTZ NOT NULL,
    collected_by     TEXT        NOT NULL DEFAULT '' CHECK (char_length(collected_by) <= 120),
    printed_by       BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    printed_by_name  TEXT        NOT NULL CHECK (char_length(printed_by_name) <= 120),
    printed_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT specimen_label_log_patient_fkey FOREIGN KEY (patient_id, practice_id)
        REFERENCES patient (id, practice_id) ON DELETE CASCADE
);
CREATE INDEX specimen_label_log_patient_idx ON specimen_label_log (patient_id, printed_at DESC);
CREATE INDEX specimen_label_log_practice_idx ON specimen_label_log (practice_id, printed_at DESC);
CREATE INDEX specimen_label_log_appointment_idx ON specimen_label_log (appointment_id);
CREATE INDEX specimen_label_log_printed_by_idx ON specimen_label_log (printed_by);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS specimen_label_log;
DROP TABLE IF EXISTS sterile_pack_use;
DROP TABLE IF EXISTS sterile_pack;
DROP TABLE IF EXISTS sterilization_cycle;
DROP INDEX IF EXISTS equipment_label_code_key;
ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_id_practice_key;
ALTER TABLE equipment DROP COLUMN IF EXISTS label_code;
ALTER TABLE patient DROP CONSTRAINT IF EXISTS patient_birth_date_year_check;
ALTER TABLE patient DROP COLUMN IF EXISTS birth_date;
ALTER TABLE practice DROP COLUMN IF EXISTS label_settings;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
