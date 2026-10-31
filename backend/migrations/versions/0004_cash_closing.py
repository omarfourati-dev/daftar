"""Cash closing of a day, verified by the owner (section 16.3).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cash_closing (
            practice_id            BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
            day                    DATE        NOT NULL,
            expected_cash_millimes BIGINT      NOT NULL CHECK (expected_cash_millimes >= 0),
            counted_cash_millimes  BIGINT      NOT NULL CHECK (counted_cash_millimes >= 0),
            note                   TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
            closed_by              BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
            closed_at              TIMESTAMPTZ NOT NULL,
            verified_by            BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
            verified_at            TIMESTAMPTZ NULL,
            CONSTRAINT cash_closing_pkey PRIMARY KEY (practice_id, day)
        );
        CREATE INDEX cash_closing_unverified_idx ON cash_closing (practice_id, day) WHERE verified_at IS NULL;
        CREATE INDEX cash_closing_closed_by_idx ON cash_closing (closed_by);
        CREATE INDEX cash_closing_verified_by_idx ON cash_closing (verified_by);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cash_closing;")
