"""The hygiene register becomes a document (review H1 of stock-hygiène): every due date is written down as its own
row, so a later change of the plan, of the opening hours or a deactivation never rewrites the past.

- ``hygiene_task_due``: one row per task and due date with its status – ``open`` (to do, or overdue while it is the
  task's current occurrence), ``done`` (a proof exists) or ``missed`` (a newer occurrence replaced it, or the task was
  deactivated, without a proof). Title and equipment are copied into the row: renaming a task or a device later does
  not change what an inspection reads for the past. The app writes the rows up to today – hourly by a job and on
  every read in case the job did not run (:mod:`daftar.hygiene_register`).
- ``hygiene_task.materialized_until``: the last day whose rows are written (NULL: none yet – the app starts at the
  day the task was created).

Existing proofs keep their row (status ``done``); the open and missed rows of existing tasks are written by the app at
the first read. Additive and safe on the live database.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-01
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UPGRADE = """
ALTER TABLE hygiene_task ADD COLUMN materialized_until DATE NULL;

CREATE TABLE hygiene_task_due (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id     BIGINT  NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    task_id         BIGINT  NOT NULL,
    due_on          DATE    NOT NULL,
    title           TEXT    NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    equipment_id    BIGINT  NULL REFERENCES equipment (id) ON DELETE SET NULL,
    equipment_name  TEXT    NULL CHECK (char_length(equipment_name) <= 120),
    status          TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'missed')),
    CONSTRAINT hygiene_task_due_task_fkey FOREIGN KEY (task_id, practice_id) REFERENCES hygiene_task (id, practice_id),
    CONSTRAINT hygiene_task_due_once UNIQUE (task_id, due_on)
);
CREATE INDEX hygiene_task_due_practice_idx ON hygiene_task_due (practice_id, due_on DESC);
-- the navigation badge counts the open rows of a practice every minute
CREATE INDEX hygiene_task_due_open_idx ON hygiene_task_due (practice_id) WHERE status = 'open';
CREATE INDEX hygiene_task_due_equipment_idx ON hygiene_task_due (equipment_id);

INSERT INTO hygiene_task_due (practice_id, task_id, due_on, title, equipment_id, equipment_name, status)
SELECT d.practice_id, d.task_id, d.due_on, t.title, t.equipment_id, e.name, 'done'
FROM hygiene_task_done d
JOIN hygiene_task t ON t.id = d.task_id
LEFT JOIN equipment e ON e.id = t.equipment_id;
"""

DOWNGRADE = """
DROP TABLE IF EXISTS hygiene_task_due;
ALTER TABLE hygiene_task DROP COLUMN IF EXISTS materialized_until;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
