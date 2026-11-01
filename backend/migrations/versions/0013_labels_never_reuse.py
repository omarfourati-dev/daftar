"""Labels: a code is never given twice, a cycle is cancelled instead of deleted, the traceability outlives the patient,
"done by" is chosen (review of the labels H1, M4, N6).

Additive and safe on the live database – new columns with defaults, small tables:

- ``practice.autoclave_codes_given``: how many autoclave codes (``A1``, ``A2`` …) the practice has given; the next
  autoclave gets the one after – never a code given before, also when its autoclave is gone. Starts at the highest
  code given so far.
- ``equipment.last_cycle_number``: the last cycle number given to the autoclave; the next cycle gets the one after –
  never a number given before (a cancelled cycle keeps its number). Starts at the highest number given so far – of
  the cycles there and of those deleted before (named in the change log).
- ``sterilization_cycle.cancelled_at`` / ``cancelled_by`` / ``cancelled_by_name`` / ``cancel_reason``: the owner
  cancels a cycle entered by mistake; it keeps its number and its pack codes, its packs can no longer be used.
  ``recorded_by`` / ``recorded_by_name``: who entered the cycle (``performed_by`` is who ran it – chosen, by default
  the same person); existing cycles were entered by who ran them.
- ``sterile_pack``: the packs stay with their cycle – the reference no longer cascades (cycles are never deleted).
- ``sterile_pack_use``: erasing a patient keeps the use, so the pack stays used: the app sets ``patient_id`` to NULL
  before the patient row goes (the reference no longer cascades – a forgotten step fails instead of losing the trace);
  ``patient_no`` keeps the patient's number, nothing else.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-01
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UPGRADE = """
ALTER TABLE practice ADD COLUMN autoclave_codes_given INTEGER NOT NULL DEFAULT 0
    CHECK (autoclave_codes_given BETWEEN 0 AND 99);
UPDATE practice p SET autoclave_codes_given = given.n
FROM (SELECT practice_id, max(substring(label_code FROM 2)::integer) AS n
      FROM equipment WHERE label_code IS NOT NULL GROUP BY practice_id) AS given
WHERE given.practice_id = p.id;

ALTER TABLE equipment ADD COLUMN last_cycle_number INTEGER NOT NULL DEFAULT 0
    CHECK (last_cycle_number BETWEEN 0 AND 999999);
UPDATE equipment e SET last_cycle_number = numbers.n
FROM (SELECT equipment_id, max(number) AS n FROM sterilization_cycle GROUP BY equipment_id) AS numbers
WHERE numbers.equipment_id = e.id;
-- a cycle deleted before (0012) gave its number too: the change log names it "A1 n° 413"
UPDATE equipment e SET last_cycle_number = greatest(e.last_cycle_number, gone.n)
FROM (SELECT practice_id, split_part(before ->> 'cycle', ' n° ', 1) AS code,
             max(split_part(before ->> 'cycle', ' n° ', 2)::integer) AS n
      FROM audit_log
      WHERE entity = 'sterilization_cycle' AND action = 'delete' AND before ->> 'cycle' ~ '^A[0-9]{1,2} n° [0-9]{1,6}$'
      GROUP BY 1, 2) AS gone
WHERE e.practice_id = gone.practice_id AND e.label_code = gone.code;

ALTER TABLE sterilization_cycle
    ADD COLUMN recorded_by BIGINT NULL REFERENCES app_user (id) ON DELETE SET NULL,
    ADD COLUMN recorded_by_name TEXT NOT NULL DEFAULT '' CHECK (char_length(recorded_by_name) <= 120),
    ADD COLUMN cancelled_at TIMESTAMPTZ NULL,
    ADD COLUMN cancelled_by BIGINT NULL REFERENCES app_user (id) ON DELETE SET NULL,
    ADD COLUMN cancelled_by_name TEXT NULL CHECK (char_length(cancelled_by_name) <= 120),
    ADD COLUMN cancel_reason TEXT NULL CHECK (char_length(cancel_reason) BETWEEN 1 AND 300),
    ADD CONSTRAINT sterilization_cycle_cancel_check CHECK (
        (cancelled_at IS NULL) = (cancel_reason IS NULL) AND (cancelled_at IS NULL) = (cancelled_by_name IS NULL));
UPDATE sterilization_cycle SET recorded_by = performed_by, recorded_by_name = performed_by_name;
CREATE INDEX sterilization_cycle_recorded_by_idx ON sterilization_cycle (recorded_by);
CREATE INDEX sterilization_cycle_cancelled_by_idx ON sterilization_cycle (cancelled_by);

ALTER TABLE sterile_pack DROP CONSTRAINT sterile_pack_cycle_fkey;
ALTER TABLE sterile_pack ADD CONSTRAINT sterile_pack_cycle_fkey FOREIGN KEY (cycle_id, practice_id)
    REFERENCES sterilization_cycle (id, practice_id);

ALTER TABLE sterile_pack_use ADD COLUMN patient_no BIGINT NULL;
UPDATE sterile_pack_use SET patient_no = patient_id;
ALTER TABLE sterile_pack_use ALTER COLUMN patient_no SET NOT NULL;
ALTER TABLE sterile_pack_use ALTER COLUMN patient_id DROP NOT NULL;
ALTER TABLE sterile_pack_use DROP CONSTRAINT sterile_pack_use_patient_fkey;
ALTER TABLE sterile_pack_use ADD CONSTRAINT sterile_pack_use_patient_fkey FOREIGN KEY (patient_id, practice_id)
    REFERENCES patient (id, practice_id);
ALTER TABLE sterile_pack_use ADD CONSTRAINT sterile_pack_use_patient_no_check
    CHECK (patient_id IS NULL OR patient_no = patient_id);
"""

DOWNGRADE = """
DELETE FROM sterile_pack_use WHERE patient_id IS NULL;
ALTER TABLE sterile_pack_use DROP CONSTRAINT IF EXISTS sterile_pack_use_patient_no_check;
ALTER TABLE sterile_pack_use DROP CONSTRAINT IF EXISTS sterile_pack_use_patient_fkey;
ALTER TABLE sterile_pack_use ADD CONSTRAINT sterile_pack_use_patient_fkey FOREIGN KEY (patient_id, practice_id)
    REFERENCES patient (id, practice_id) ON DELETE CASCADE;
ALTER TABLE sterile_pack_use ALTER COLUMN patient_id SET NOT NULL;
ALTER TABLE sterile_pack_use DROP COLUMN IF EXISTS patient_no;

ALTER TABLE sterile_pack DROP CONSTRAINT IF EXISTS sterile_pack_cycle_fkey;
ALTER TABLE sterile_pack ADD CONSTRAINT sterile_pack_cycle_fkey FOREIGN KEY (cycle_id, practice_id)
    REFERENCES sterilization_cycle (id, practice_id) ON DELETE CASCADE;

DROP INDEX IF EXISTS sterilization_cycle_cancelled_by_idx;
DROP INDEX IF EXISTS sterilization_cycle_recorded_by_idx;
ALTER TABLE sterilization_cycle
    DROP CONSTRAINT IF EXISTS sterilization_cycle_cancel_check,
    DROP COLUMN IF EXISTS cancel_reason,
    DROP COLUMN IF EXISTS cancelled_by_name,
    DROP COLUMN IF EXISTS cancelled_by,
    DROP COLUMN IF EXISTS cancelled_at,
    DROP COLUMN IF EXISTS recorded_by_name,
    DROP COLUMN IF EXISTS recorded_by;

ALTER TABLE equipment DROP COLUMN IF EXISTS last_cycle_number;
ALTER TABLE practice DROP COLUMN IF EXISTS autoclave_codes_given;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
