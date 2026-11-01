"""Labels: a mistyped cycle number no longer sets the counter of the autoclave for good, the change log forgets the
name of an erased patient (review of the labels fix, Mi2 and Mi1).

Additive and safe on the live database – two nullable columns, one small update of today's change log:

- ``equipment.skipped_from`` / ``skipped_to``: the numbers the last jump of the counter skipped (413 → 4130: 414 to
  4129) – never given. Once the cycle that jumped is cancelled (or the next cycle is typed just above the last
  regular one), the next number comes from them, the lowest first: the last number entered + 1, never one given
  before. The counter (``last_cycle_number``) still only counts up. Existing autoclaves start without.
- ``audit_log``: a use of a pack taken back keeps the patient's id and number with his name, so that erasing the
  patient takes the name out (the app does it from now on). The entries written since the labels went live get them
  where the name is that of exactly one patient of the practice; the others stay as they are.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-01
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

UPGRADE = """
ALTER TABLE equipment
    ADD COLUMN skipped_from INTEGER NULL,
    ADD COLUMN skipped_to INTEGER NULL,
    ADD CONSTRAINT equipment_skipped_check CHECK (
        (skipped_from IS NULL) = (skipped_to IS NULL)
        AND (skipped_from IS NULL OR (1 <= skipped_from AND skipped_from <= skipped_to
                                      AND skipped_to < last_cycle_number)));

UPDATE audit_log a SET before = a.before || jsonb_build_object('patientId', m.patient_id, 'patientNo', m.patient_id)
FROM (SELECT e.id AS entry_id, min(p.id) AS patient_id
      FROM audit_log e
      JOIN patient p ON p.practice_id = e.practice_id AND btrim(p.first_name || ' ' || p.last_name) = e.before ->> 'patient'
      WHERE e.entity = 'sterile_pack_use' AND e.action = 'delete' AND e.before -> 'patientId' IS NULL
      GROUP BY e.id
      HAVING count(*) = 1) AS m
WHERE a.id = m.entry_id;
"""

DOWNGRADE = """
ALTER TABLE equipment
    DROP CONSTRAINT IF EXISTS equipment_skipped_check,
    DROP COLUMN IF EXISTS skipped_to,
    DROP COLUMN IF EXISTS skipped_from;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
