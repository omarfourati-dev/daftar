"""Hygiene and maintenance: equipment, recurring tasks and their proof (spec stock-hygiène 5.1).

New tables, nothing existing changes – safe on the live database:

- ``equipment``: autoclave, washer-disinfector, ultrasonic bath, compressor, suction, dental unit, X-ray, other;
- ``hygiene_task``: a recurring task (daily on opening days, weekly on a weekday, monthly, yearly, every N days from
  ``starts_on``), optionally for one piece of equipment, with instructions;
- ``hygiene_task_done``: one proof per task and due date – who (the name is kept with it), when, ok / not ok, note.
  A task with proofs cannot be deleted (plain reference, checked at the end of the statement – deleting the whole
  practice still works); the API deactivates it instead, so the history an inspection asks for stays complete.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-31
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

KINDS = "'autoclave', 'thermodesinfecteur', 'ultrasons', 'compresseur', 'aspiration', 'fauteuil', 'radiographie', 'autre'"
FREQUENCIES = "'daily', 'weekly', 'monthly', 'yearly', 'every_n_days'"

UPGRADE = f"""
CREATE TABLE equipment (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id    BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name           TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    kind           TEXT        NOT NULL DEFAULT 'autre' CHECK (kind IN ({KINDS})),
    serial_number  TEXT        NOT NULL DEFAULT '' CHECK (char_length(serial_number) <= 60),
    note           TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    active         BOOLEAN     NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX equipment_name_key ON equipment (practice_id, lower(name));

CREATE TABLE hygiene_task (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id    BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    title          TEXT        NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    equipment_id   BIGINT      NULL REFERENCES equipment (id) ON DELETE SET NULL,
    frequency      TEXT        NOT NULL CHECK (frequency IN ({FREQUENCIES})),
    weekday        INTEGER     NULL CHECK (weekday BETWEEN 1 AND 7),
    interval_days  INTEGER     NULL CHECK (interval_days BETWEEN 2 AND 365),
    starts_on      DATE        NOT NULL,
    instructions   TEXT        NOT NULL DEFAULT '' CHECK (char_length(instructions) <= 1000),
    active         BOOLEAN     NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT hygiene_task_id_practice_key UNIQUE (id, practice_id),
    -- the weekday only for weekly tasks, the interval only for "every N days"
    CONSTRAINT hygiene_task_rhythm_check CHECK (
        (frequency = 'weekly') = (weekday IS NOT NULL) AND (frequency = 'every_n_days') = (interval_days IS NOT NULL)
    )
);
CREATE INDEX hygiene_task_practice_idx ON hygiene_task (practice_id);
CREATE INDEX hygiene_task_equipment_idx ON hygiene_task (equipment_id);

CREATE TABLE hygiene_task_done (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id   BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    task_id       BIGINT      NOT NULL,
    due_on        DATE        NOT NULL,
    done_by       BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    done_by_name  TEXT        NOT NULL DEFAULT '' CHECK (char_length(done_by_name) <= 120),
    done_at       TIMESTAMPTZ NOT NULL,
    result        TEXT        NOT NULL DEFAULT 'ok' CHECK (result IN ('ok', 'not_ok')),
    note          TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    CONSTRAINT hygiene_task_done_task_fkey FOREIGN KEY (task_id, practice_id) REFERENCES hygiene_task (id, practice_id),
    CONSTRAINT hygiene_task_done_once UNIQUE (task_id, due_on)
);
CREATE INDEX hygiene_task_done_practice_idx ON hygiene_task_done (practice_id, due_on DESC);
CREATE INDEX hygiene_task_done_by_idx ON hygiene_task_done (done_by);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS hygiene_task_done;
DROP TABLE IF EXISTS hygiene_task;
DROP TABLE IF EXISTS equipment;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
