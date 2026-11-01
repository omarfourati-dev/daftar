"""Stock (material) of a practice and the change log (spec 2026-10-31 stock-hygiène, sections 4 and 8).

New tables, nothing existing changes – safe on the live database:

- ``supplier``: who delivers (phone and WhatsApp as E.164 like everywhere);
- ``stock_product``: what the practice keeps in stock, with category, unit, default supplier and a minimum quantity
  (the alarm threshold); a name exists once per practice (without case);
- ``stock_receipt`` + ``stock_receipt_line``: deliveries (date, supplier, delivery note number; per line product,
  quantity, unit price in millimes, lot and expiry date – all optional except product and quantity);
- ``stock_movement``: every change of stock in one table – ``receipt`` (+, one per receipt line), ``use`` (−,
  optionally for an act and/or an appointment), ``adjust`` (± inventory count, with a reason), ``waste`` (−). The stock
  of a product is the sum of its movements – there is no stored number that could drift;
- ``audit_log``: who deleted or corrected what, when, old → new (the start of the audit log of security review N4).

Tenant rule as everywhere: every row has ``practice_id``; references between the new tables are composite
``(…_id, practice_id)``, so nothing can point into another practice. References that become NULL when the other row
goes (supplier, act, appointment, user) are plain ones – the API checks that they belong to the practice.
A product or a task that has history cannot be deleted (plain ``REFERENCES``, checked at the end of the statement, so
deleting the whole practice still works); the API deactivates it instead.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-31
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

E164 = "'^\\+[1-9][0-9]{7,14}$'"
CATEGORIES = (
    "'hygiene', 'anesthesie', 'restauration', 'endodontie', 'prothese', 'chirurgie', 'prelevements', 'injection', "
    "'pansements', 'bureau', 'autre'"
)
UNITS = "'piece', 'boite', 'flacon', 'carpule', 'paquet', 'sachet', 'tube', 'rouleau', 'paire', 'ml', 'g'"
MAX_QUANTITY = 100_000
MAX_MILLIMES = 100_000_000

UPGRADE = f"""
CREATE TABLE supplier (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name         TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    phone        TEXT        NULL CHECK (phone ~ {E164}),
    whatsapp     TEXT        NULL CHECK (whatsapp ~ {E164}),
    note         TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    active       BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX supplier_name_key ON supplier (practice_id, lower(name));

CREATE TABLE stock_product (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id   BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    name          TEXT        NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    category      TEXT        NOT NULL DEFAULT 'autre' CHECK (category IN ({CATEGORIES})),
    unit          TEXT        NOT NULL DEFAULT 'piece' CHECK (unit IN ({UNITS})),
    supplier_id   BIGINT      NULL REFERENCES supplier (id) ON DELETE SET NULL,
    min_quantity  INTEGER     NOT NULL DEFAULT 0 CHECK (min_quantity BETWEEN 0 AND {MAX_QUANTITY}),
    note          TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    ean           TEXT        NULL CHECK (ean ~ '^[0-9]{{8,14}}$'),
    active        BOOLEAN     NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stock_product_id_practice_key UNIQUE (id, practice_id)
);
CREATE UNIQUE INDEX stock_product_name_key ON stock_product (practice_id, lower(name));
CREATE INDEX stock_product_supplier_idx ON stock_product (supplier_id);

CREATE TABLE stock_receipt (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    received_on  DATE        NOT NULL,
    supplier_id  BIGINT      NULL REFERENCES supplier (id) ON DELETE SET NULL,
    reference    TEXT        NOT NULL DEFAULT '' CHECK (char_length(reference) <= 60),
    note         TEXT        NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    created_by   BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stock_receipt_id_practice_key UNIQUE (id, practice_id)
);
CREATE INDEX stock_receipt_practice_idx ON stock_receipt (practice_id, received_on DESC);
CREATE INDEX stock_receipt_supplier_idx ON stock_receipt (supplier_id);
CREATE INDEX stock_receipt_created_by_idx ON stock_receipt (created_by);

CREATE TABLE stock_receipt_line (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id          BIGINT  NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    receipt_id           BIGINT  NOT NULL,
    product_id           BIGINT  NOT NULL,
    quantity             INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND {MAX_QUANTITY}),
    unit_price_millimes  BIGINT  NULL CHECK (unit_price_millimes BETWEEN 0 AND {MAX_MILLIMES}),
    lot                  TEXT    NOT NULL DEFAULT '' CHECK (char_length(lot) <= 60),
    expires_on           DATE    NULL,
    CONSTRAINT stock_receipt_line_id_practice_key UNIQUE (id, practice_id),
    CONSTRAINT stock_receipt_line_receipt_fkey FOREIGN KEY (receipt_id, practice_id)
        REFERENCES stock_receipt (id, practice_id) ON DELETE CASCADE,
    CONSTRAINT stock_receipt_line_product_fkey FOREIGN KEY (product_id, practice_id)
        REFERENCES stock_product (id, practice_id)
);
CREATE INDEX stock_receipt_line_receipt_idx ON stock_receipt_line (receipt_id);
CREATE INDEX stock_receipt_line_product_idx ON stock_receipt_line (product_id);

CREATE TABLE stock_movement (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id         BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    product_id          BIGINT      NOT NULL,
    kind                TEXT        NOT NULL CHECK (kind IN ('receipt', 'use', 'adjust', 'waste')),
    quantity            INTEGER     NOT NULL CHECK (quantity <> 0 AND quantity BETWEEN -{MAX_QUANTITY} AND {MAX_QUANTITY}),
    receipt_line_id     BIGINT      NULL,
    service_id          BIGINT      NULL REFERENCES service (id) ON DELETE SET NULL,
    appointment_id      BIGINT      NULL REFERENCES appointment (id) ON DELETE SET NULL,
    unit_cost_millimes  BIGINT      NULL CHECK (unit_cost_millimes BETWEEN 0 AND {MAX_MILLIMES}),
    reason              TEXT        NOT NULL DEFAULT '' CHECK (char_length(reason) <= 300),
    created_by          BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stock_movement_product_fkey FOREIGN KEY (product_id, practice_id)
        REFERENCES stock_product (id, practice_id),
    CONSTRAINT stock_movement_line_fkey FOREIGN KEY (receipt_line_id, practice_id)
        REFERENCES stock_receipt_line (id, practice_id) ON DELETE CASCADE,
    CONSTRAINT stock_movement_line_key UNIQUE (receipt_line_id),
    -- receipts add and come from a receipt line; use and waste take away; an inventory count says why
    CONSTRAINT stock_movement_sign_check CHECK (
        (kind = 'receipt' AND quantity > 0 AND receipt_line_id IS NOT NULL)
        OR (kind IN ('use', 'waste') AND quantity < 0 AND receipt_line_id IS NULL)
        OR (kind = 'adjust' AND receipt_line_id IS NULL AND char_length(reason) >= 1)
    )
);
CREATE INDEX stock_movement_product_idx ON stock_movement (product_id, created_at DESC);
CREATE INDEX stock_movement_practice_idx ON stock_movement (practice_id, created_at DESC);
CREATE INDEX stock_movement_service_idx ON stock_movement (service_id);
CREATE INDEX stock_movement_appointment_idx ON stock_movement (appointment_id);
CREATE INDEX stock_movement_created_by_idx ON stock_movement (created_by);

CREATE TABLE audit_log (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    practice_id  BIGINT      NOT NULL REFERENCES practice (id) ON DELETE CASCADE,
    user_id      BIGINT      NULL REFERENCES app_user (id) ON DELETE SET NULL,
    user_name    TEXT        NOT NULL DEFAULT '' CHECK (char_length(user_name) <= 120),
    at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    entity       TEXT        NOT NULL CHECK (entity ~ '^[a-z_]{{1,40}}$'),
    entity_id    BIGINT      NOT NULL,
    action       TEXT        NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    before       JSONB       NULL,
    after        JSONB       NULL,
    reason       TEXT        NOT NULL DEFAULT '' CHECK (char_length(reason) <= 300)
);
CREATE INDEX audit_log_practice_idx ON audit_log (practice_id, at DESC);
CREATE INDEX audit_log_user_idx ON audit_log (user_id);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS stock_movement;
DROP TABLE IF EXISTS stock_receipt_line;
DROP TABLE IF EXISTS stock_receipt;
DROP TABLE IF EXISTS stock_product;
DROP TABLE IF EXISTS supplier;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
