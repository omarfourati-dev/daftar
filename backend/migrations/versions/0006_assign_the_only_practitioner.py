"""Give appointments without practitioner the practice's only active practitioner (code review H1).

Until now an appointment "Non attribué" lay in its own calendar next to the doctor's: online, by phone or in the
doctor's column the same time could be booked a second time. From now on every appointment of a practice with active
practitioners has one (daftar/scheduling.py ``choose_practitioner``). This migration moves the existing ones of
practices with **exactly one** active practitioner into that practitioner's calendar:

- only appointments that are not cancelled (no-shows too – they block nothing, but count for the doctor);
- an appointment that would overlap one already in the practitioner's calendar keeps its "no practitioner" calendar
  (the EXCLUDE constraint would refuse it) – the migration does not stop for it; the practice sees both in the agenda
  and moves one of them;
- practices with several practitioners keep their old appointments as they are (whom to give them to is a decision of
  the practice; moving or reopening such an appointment gives it the first free practitioner).

Unassigned appointments never overlap each other (the EXCLUDE constraint on the "no practitioner" calendar), so one
``UPDATE`` that checks against the practitioner's existing appointments cannot collide with itself.

Downgrade: deliberately nothing – which appointment had no practitioner before is not kept, and an appointment with
its practitioner is valid under the old rules too.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-31
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

ASSIGN = """
WITH only_one AS (
    SELECT practice_id, min(id) AS practitioner_id
    FROM practitioner
    WHERE active
    GROUP BY practice_id
    HAVING count(*) = 1
)
UPDATE appointment AS a
SET practitioner_id = o.practitioner_id
FROM only_one AS o
WHERE a.practice_id = o.practice_id
  AND a.practitioner_id IS NULL
  AND a.status <> 'cancelled'
  AND (
      a.status = 'no_show'
      OR NOT EXISTS (
          SELECT 1
          FROM appointment AS b
          WHERE b.practice_id = a.practice_id
            AND b.practitioner_id = o.practitioner_id
            AND b.status NOT IN ('cancelled', 'no_show')
            AND tstzrange(b.starts_at, b.ends_at) && tstzrange(a.starts_at, a.ends_at)
      )
  );
"""


def upgrade() -> None:
    op.execute(ASSIGN)


def downgrade() -> None:
    pass
