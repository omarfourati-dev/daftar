"""Section 15: onboarding state of a practice, medical alerts limited to 500 characters.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE practice
            ADD COLUMN onboarding JSONB NOT NULL DEFAULT '{}'::jsonb,
            ADD CONSTRAINT practice_onboarding_check CHECK (jsonb_typeof(onboarding) = 'object');
        ALTER TABLE patient DROP CONSTRAINT patient_alerts_check;
        ALTER TABLE patient ADD CONSTRAINT patient_alerts_check CHECK (char_length(alerts) <= 500);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE patient DROP CONSTRAINT patient_alerts_check;
        ALTER TABLE patient ADD CONSTRAINT patient_alerts_check CHECK (char_length(alerts) <= 1000);
        ALTER TABLE practice DROP CONSTRAINT practice_onboarding_check, DROP COLUMN onboarding;
        """
    )
