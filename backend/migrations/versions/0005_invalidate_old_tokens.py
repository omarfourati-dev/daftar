"""Invalidate every sign-in token issued before this deploy (security review M3).

Until fixlist 1 the app ran on the main domain, so tokens of that time may still lie in the main domain's
localStorage – next to the AdSense scripts of the landing page now. ``token_version`` is part of every token
(daftar/tokens.py); raising it by one for every account makes all older tokens fail with 401, exactly like
"sign out everywhere". Users simply sign in again; passwords and everything else stay.

- On a database with data: one ``UPDATE`` for all rows. Alembic runs it once; should it run again (downgrade and
  upgrade), it signs everybody out once more – harmless.
- Downgrade: deliberately nothing. Lowering the versions again would revive the old tokens and invalidate the ones
  issued since.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE app_user SET token_version = token_version + 1;")


def downgrade() -> None:
    pass
