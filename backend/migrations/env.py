"""Alembic environment: online migrations only, URL from DATABASE_URL (or a connection passed by the tests)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from daftar.settings import normalize_database_url

config = context.config


def run() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL is missing")
    engine = create_engine(normalize_database_url(url), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline migrations are not supported")
run()
