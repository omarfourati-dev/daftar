"""Shared fixtures – against a real PostgreSQL (default: container ``daftar-postgres`` on port 55436, DB ``daftar_test``).

- the schema is migrated once per run (upgrade → downgrade → upgrade, so both directions are exercised);
- ``db`` empties every table before a test; ``client`` is a TestClient of a fresh app with a fixed clock;
- factories insert rows directly: ``make_practice`` (optionally with practitioners), ``make_practitioner``,
  ``make_service``, ``make_user``, ``make_patient``, ``make_appointment``, ``make_queue_entry``, ``make_treatment``,
  ``make_payment``, ``make_invitation``;
- ``auth_headers(user)`` → ``{"Authorization": "Bearer …"}`` for that user.

Feature tests can put their own fixtures into their test module (or a ``conftest.py`` in a sub-folder), so parallel
work does not collide here.
"""

from __future__ import annotations

import itertools
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import Engine, Row, create_engine, insert, select, text
from sqlalchemy.engine import make_url

from daftar import passwords
from daftar.app import create_app
from daftar.clock import FixedClock, today_tunis
from daftar.db import make_engine
from daftar.invitations import create_invitation
from daftar.settings import Settings
from daftar.tables import (
    ALL_TABLES,
    app_user,
    appointment,
    patient,
    payment,
    practice,
    practitioner,
    queue_entry,
    service,
    treatment,
)

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://daftar:daftar@localhost:55436/daftar_test"
)
JWT_SECRET = "test-jwt-secret-that-is-long-enough-0123456789"
#: Friday 30.10.2026, 09:00 in Tunis (08:00 UTC).
T0 = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
PASSWORD = "mot-de-passe-solide"


# --- database -----------------------------------------------------------------------------------------------------

def _ensure_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}).first()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def _alembic(conn: Any) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["connection"] = conn
    return cfg


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _ensure_database(TEST_DATABASE_URL)
    eng = make_engine(TEST_DATABASE_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    with eng.begin() as conn:
        command.upgrade(_alembic(conn), "head")
        command.downgrade(_alembic(conn), "base")
        command.upgrade(_alembic(conn), "head")
    yield eng
    eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def fast_password_hashing() -> Iterator[None]:
    """Argon2 with minimal cost – the production parameters would make the suite slow."""
    passwords.use_hasher(PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    yield


@pytest.fixture
def db(engine: Engine) -> Engine:
    """The engine, with every table emptied (identities restarted) before the test."""
    names = ", ".join(t.name for t in ALL_TABLES)  # not the reference data (plans)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    return engine


# --- app ----------------------------------------------------------------------------------------------------------

@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T0)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret=JWT_SECRET,
        landing_dir=FIXTURES / "landing",
        web_dir=FIXTURES / "web",
        log_requests=False,
    )


@pytest.fixture
def app(db: Engine, settings: Settings, clock: FixedClock):  # type: ignore[no-untyped-def]
    return create_app(settings, clock, engine=db, run_jobs=False)


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        yield c


# --- factories ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class TestUser:
    __test__ = False
    id: int
    email: str
    password: str
    role: str
    practice_id: int | None
    name: str


_seq = itertools.count(1)


def _insert(engine: Engine, table: Any, values: dict[str, Any]) -> Row[Any]:
    with engine.begin() as conn:
        return conn.execute(insert(table).values(**values).returning(table)).one()


class PracticeRow:
    """A practice row (attribute access like a SQLAlchemy Row) plus the practitioners created with it."""

    def __init__(self, row: Row[Any], practitioners: list[Row[Any]]) -> None:
        self._row = row
        self.practitioners = practitioners

    def __getattr__(self, name: str) -> Any:
        return getattr(self._row, name)


@pytest.fixture
def make_practice(db: Engine, clock: FixedClock) -> Callable[..., PracticeRow]:
    """``make_practice("Cabinet X", specialty="dentiste", practitioners=["Dr. A"], status="active")``.

    Defaults: slug ``cabinet-<n>``, specialty ``generaliste``, plan pilot, opening hours Mon–Sat 08:00–12:30 and
    14:00–18:00 (database defaults); no practitioners unless asked.
    """

    def make(
        name: str | None = None,
        *,
        slug: str | None = None,
        specialty: str = "generaliste",
        practitioners: list[str] | int = 0,
        **values: Any,
    ) -> PracticeRow:
        n = next(_seq)
        row = _insert(
            db,
            practice,
            {"name": name or f"Cabinet {n}", "slug": slug or f"cabinet-{n}", "specialty": specialty,
             "created_at": clock.now(), **values},
        )
        names = [f"Dr. Praticien {i}" for i in range(1, practitioners + 1)] if isinstance(practitioners, int) else practitioners
        made = [
            _insert(db, practitioner, {"practice_id": row.id, "name": doctor, "sort": i})
            for i, doctor in enumerate(names, start=1)
        ]
        return PracticeRow(row, made)

    return make


@pytest.fixture
def make_practitioner(db: Engine) -> Callable[..., Row[Any]]:
    def make(practice_row: Any, name: str | None = None, **values: Any) -> Row[Any]:
        return _insert(db, practitioner, {"practice_id": practice_row.id, "name": name or f"Dr. {next(_seq)}", **values})

    return make


@pytest.fixture
def make_service(db: Engine) -> Callable[..., Row[Any]]:
    def make(practice_row: Any, name_fr: str = "Consultation", duration_min: int = 30, **values: Any) -> Row[Any]:
        return _insert(db, service, {"practice_id": practice_row.id, "name_fr": name_fr, "duration_min": duration_min, **values})

    return make


@pytest.fixture
def make_user(db: Engine, clock: FixedClock, make_practice: Callable[..., PracticeRow]) -> Callable[..., TestUser]:
    """``make_user(practice, "dentist")``; without a practice a new one is created (except for ``"admin"``)."""

    def make(
        practice_row: Any | None = None,
        role: str = "owner",
        *,
        email: str | None = None,
        password: str = PASSWORD,
        name: str | None = None,
        lang: str = "fr",
    ) -> TestUser:
        n = next(_seq)
        practice_id = None
        if role != "admin":
            practice_id = (practice_row or make_practice()).id
        row = _insert(
            db,
            app_user,
            {
                "email": (email or f"user{n}@daftar.test").lower(),
                "password_hash": passwords.hash_password(password),
                "practice_id": practice_id,
                "role": role,
                "name": name if name is not None else f"Utilisateur {n}",
                "lang": lang,
                "created_at": clock.now(),
            },
        )
        return TestUser(row.id, row.email, password, row.role, row.practice_id, row.name)

    return make


@pytest.fixture
def auth_headers(app) -> Callable[[TestUser], dict[str, str]]:  # type: ignore[no-untyped-def]
    ctx = app.state.ctx

    def headers(user: TestUser) -> dict[str, str]:
        with ctx.engine.connect() as conn:
            version = conn.execute(select(app_user.c.token_version).where(app_user.c.id == user.id)).scalar_one()
        return {"Authorization": f"Bearer {ctx.tokens.issue(user.id, version)}"}

    return headers


@pytest.fixture
def make_patient(db: Engine, clock: FixedClock) -> Callable[..., Row[Any]]:
    def make(practice_row: Any, **values: Any) -> Row[Any]:
        n = next(_seq)
        return _insert(
            db,
            patient,
            {
                "practice_id": practice_row.id,
                "first_name": f"Prénom{n}",
                "last_name": f"Nom{n}",
                "phone": f"+21600{n:06d}",
                "created_at": clock.now(),
                **values,
            },
        )

    return make


@pytest.fixture
def make_appointment(db: Engine, clock: FixedClock) -> Callable[..., Row[Any]]:
    """``make_appointment(patient, starts_at=…, duration_min=30, practitioner_id=…)`` – ``ends_at`` is derived."""

    def make(
        patient_row: Row[Any], *, starts_at: datetime | None = None, duration_min: int = 30, **values: Any
    ) -> Row[Any]:
        start = starts_at or clock.now() + timedelta(hours=1)
        return _insert(
            db,
            appointment,
            {
                "practice_id": patient_row.practice_id,
                "patient_id": patient_row.id,
                "starts_at": start,
                "duration_min": duration_min,
                "ends_at": start + timedelta(minutes=duration_min),
                "created_at": clock.now(),
                **values,
            },
        )

    return make


@pytest.fixture
def make_queue_entry(db: Engine, clock: FixedClock) -> Callable[..., Row[Any]]:
    def make(practice_row: Any, ticket_no: int, *, day: date | None = None, **values: Any) -> Row[Any]:
        return _insert(
            db,
            queue_entry,
            {
                "practice_id": practice_row.id,
                "day": day or today_tunis(clock),
                "ticket_no": ticket_no,
                "arrived_at": clock.now(),
                **values,
            },
        )

    return make


@pytest.fixture
def make_treatment(db: Engine, clock: FixedClock) -> Callable[..., Row[Any]]:
    def make(patient_row: Row[Any], price_millimes: int, **values: Any) -> Row[Any]:
        return _insert(
            db,
            treatment,
            {
                "practice_id": patient_row.practice_id,
                "patient_id": patient_row.id,
                "label": "Détartrage",
                "price_millimes": price_millimes,
                "created_at": clock.now(),
                **values,
            },
        )

    return make


@pytest.fixture
def make_payment(db: Engine, clock: FixedClock) -> Callable[..., Row[Any]]:
    def make(patient_row: Row[Any], amount_millimes: int, **values: Any) -> Row[Any]:
        return _insert(
            db,
            payment,
            {
                "practice_id": patient_row.practice_id,
                "patient_id": patient_row.id,
                "amount_millimes": amount_millimes,
                "method": "cash",
                "paid_at": clock.now(),
                "created_at": clock.now(),
                **values,
            },
        )

    return make


@pytest.fixture
def make_invitation(db: Engine, clock: FixedClock) -> Callable[..., str]:
    """``make_invitation(practice, "dentist")`` → the clear token (valid 7 days from the clock)."""

    def make(practice_row: Any, role: str = "dentist", *, created_by: int | None = None) -> str:
        with db.begin() as conn:
            return create_invitation(
                conn, practice_id=practice_row.id, role=role, created_by=created_by, now=clock.now()
            ).token

    return make
