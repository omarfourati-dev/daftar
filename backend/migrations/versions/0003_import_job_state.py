"""Import jobs remember the chosen sheet and header row, keep their report after the commit, and lose the file then.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30

- ``sheet`` / ``header_row``: the choice of ``POST /api/imports/{id}/sheet`` (preview and commit read the same table);
- ``file_bytes`` becomes nullable: the commit deletes the uploaded file at once (section 14), the row – with the
  ``report`` for ``GET /api/imports/{id}/report.csv`` – stays until ``expires_at`` (24 h) and the cleanup job.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE import_job
            ADD COLUMN sheet TEXT NULL CONSTRAINT import_job_sheet_check CHECK (char_length(sheet) <= 255),
            ADD COLUMN header_row INTEGER NOT NULL DEFAULT 1 CONSTRAINT import_job_header_row_check
                CHECK (header_row BETWEEN 0 AND 20),
            ADD COLUMN report JSONB NULL,
            ALTER COLUMN file_bytes DROP NOT NULL,
            ADD CONSTRAINT import_job_file_or_commit_check CHECK (file_bytes IS NOT NULL OR committed_at IS NOT NULL);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM import_job WHERE file_bytes IS NULL;
        ALTER TABLE import_job
            DROP CONSTRAINT import_job_file_or_commit_check,
            ALTER COLUMN file_bytes SET NOT NULL,
            DROP COLUMN report,
            DROP COLUMN header_row,
            DROP COLUMN sheet;
        """
    )
