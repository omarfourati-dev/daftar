"""Database access: one SQLAlchemy engine (psycopg 3, connection pool) per app, SQLAlchemy Core only (no ORM).

In handlers take a transaction with the ``Conn`` dependency (daftar/deps.py): it commits when the handler returns
and rolls back on any exception – before the response is sent.

``hide_parameters=True``: an unexpected database error is logged with its statement but without the bound values
(names, phone numbers, hashes – security review N1).
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from .settings import normalize_database_url


def make_engine(url: str, *, pool_size: int = 5, max_overflow: int = 5) -> Engine:
    return create_engine(
        normalize_database_url(url),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
        hide_parameters=True,
    )


def ping(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def constraint_name(exc: IntegrityError) -> str | None:
    """The violated constraint, e.g. ``appointment_practitioner_no_overlap`` → answer 409 with the conflicts.

    Catch the IntegrityError around the statement (the transaction is aborted afterwards – raise an ApiError).
    """
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)
