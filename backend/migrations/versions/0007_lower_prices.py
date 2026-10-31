"""New prices (Omar, 31.10.2026): 29 DT a month instead of 49, a year 290 DT instead of 490 (still 12 months for 10).

Only the two paid plans change, and only while they still have the old price – a price the admin has changed by hand
in the meantime stays as it is. Invoices already written keep their amount (an invoice is a document).

Downgrade: back to 49 000 / 490 000, again only where the new price is still set.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-31
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

PRICES = (("cabinet_mensuel", 49_000, 29_000), ("cabinet_annuel", 490_000, 290_000))


def upgrade() -> None:
    for code, old, new in PRICES:
        op.execute(f"UPDATE plan SET price_millimes = {new} WHERE code = '{code}' AND price_millimes = {old}")


def downgrade() -> None:
    for code, old, new in PRICES:
        op.execute(f"UPDATE plan SET price_millimes = {old} WHERE code = '{code}' AND price_millimes = {new}")
