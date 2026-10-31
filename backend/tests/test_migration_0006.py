"""Migration 0006 (code review H1): appointments without practitioner go to the practice's only active practitioner."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from alembic import command
from sqlalchemy import Engine, select

from daftar.tables import appointment
from tests.conftest import _alembic

MON_9 = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)  # 09:00 in Tunis


def _doctors(db: Engine) -> dict[int, int | None]:
    with db.connect() as conn:
        return dict(conn.execute(select(appointment.c.id, appointment.c.practitioner_id)).all())  # type: ignore[arg-type]


def test_0006_gives_the_only_practitioner_and_never_creates_a_double_booking(
    db: Engine, make_practice: Callable[..., Any], make_practitioner: Callable[..., Any],
    make_patient: Callable[..., Any], make_appointment: Callable[..., Any],
) -> None:
    solo = make_practice(practitioners=["Dr. X"])
    make_practitioner(solo, "Dr. Parti", active=False)  # inactive ones do not count
    (x,) = solo.practitioners
    pat = make_patient(solo)
    plain = make_appointment(pat, starts_at=MON_9)
    done = make_appointment(pat, starts_at=MON_9 - timedelta(days=7), status="done")
    no_show = make_appointment(pat, starts_at=MON_9 - timedelta(days=6), status="no_show")
    cancelled = make_appointment(pat, starts_at=MON_9 - timedelta(days=5), status="cancelled")
    doctors_own = make_appointment(make_patient(solo), starts_at=MON_9 + timedelta(hours=2), practitioner_id=x.id)
    clash = make_appointment(make_patient(solo), starts_at=MON_9 + timedelta(hours=2, minutes=15))  # overlaps doctors_own
    duo = make_practice(practitioners=["Dr. A", "Dr. B"])
    several = make_appointment(make_patient(duo), starts_at=MON_9)
    nobody = make_practice()
    alone = make_appointment(make_patient(nobody), starts_at=MON_9)

    with db.begin() as conn:
        command.downgrade(_alembic(conn), "0005")
    with db.begin() as conn:
        command.upgrade(_alembic(conn), "head")

    assert _doctors(db) == {
        plain.id: x.id, done.id: x.id, no_show.id: x.id,
        cancelled.id: None,  # cancelled ones stay as they were
        doctors_own.id: x.id, clash.id: None,  # would be a double booking: left for the practice to sort out
        several.id: None,  # several practitioners: the practice decides
        alone.id: None,  # no practitioner at all: the one calendar
    }
