"""Dashboard (section 5 + online requests of 11.3), badges (15, C2) and monthly statistics (15, H1)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]
STATUSES = ("requested", "scheduled", "confirmed", "arrived", "in_treatment", "done", "no_show", "cancelled")


def at(hour: int, minute: int = 0, day: int = 30, month: int = 10) -> datetime:
    """A wall-clock time in Tunis (UTC+1) as UTC."""
    return datetime(2026, month, day, hour - 1, minute, tzinfo=UTC)


# --- dashboard -------------------------------------------------------------------------------------------------

def test_dashboard_of_today(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_queue_entry: Factory, make_treatment: Factory, make_payment: Factory, auth_headers: Factory, clock: Any,
) -> None:
    clock.set(at(10, 0))
    practice_row = make_practice(practitioners=2)
    d1, d2 = (p.id for p in practice_row.practitioners)
    pats = [make_patient(practice_row, reminder_consent=True) for _ in range(9)]
    make_appointment(pats[0], starts_at=at(8, 30), status="done", practitioner_id=d1)
    make_appointment(pats[1], starts_at=at(9, 0), status="no_show", practitioner_id=d1)
    make_appointment(pats[2], starts_at=at(9, 30), status="in_treatment", practitioner_id=d1)
    make_appointment(pats[3], starts_at=at(9, 45), status="arrived", practitioner_id=d2)
    up1 = make_appointment(pats[4], starts_at=at(11, 0), status="confirmed", practitioner_id=d1)
    up2 = make_appointment(pats[5], starts_at=at(10, 30), status="scheduled", practitioner_id=d2)
    make_appointment(pats[6], starts_at=at(12, 0), status="cancelled", practitioner_id=d1)
    request_today = make_appointment(pats[7], starts_at=at(15, 0), status="requested", source="online", practitioner_id=d2)
    request_later = make_appointment(pats[8], starts_at=at(9, 0, day=2, month=11), status="requested", source="online")
    make_appointment(pats[0], starts_at=at(9, 0, day=29), status="requested", source="online")  # stale: in the past
    # reminders for tomorrow: one pending, one already sent, one without consent
    make_appointment(pats[0], starts_at=at(9, 0, day=31))
    make_appointment(pats[1], starts_at=at(10, 0, day=31), reminder_sent_at=clock.now())
    make_appointment(make_patient(practice_row, reminder_consent=False), starts_at=at(11, 0, day=31))
    for n, status in enumerate(("waiting", "waiting", "called", "in_treatment", "done"), start=1):
        make_queue_entry(practice_row, n, status=status, name=f"T{n}")
    make_queue_entry(practice_row, 1, day=(T0 - timedelta(days=1)).date(), status="waiting", name="yesterday")
    make_treatment(pats[0], 100_000)
    make_payment(pats[0], 30_000, paid_at=at(9, 0))
    make_payment(pats[0], 5_000, paid_at=at(9, 0, day=29))
    make_treatment(pats[1], 20_000)
    make_payment(pats[2], 50_000, paid_at=at(9, 30))  # overpaid, does not lower the open total

    res = client.get("/api/dashboard", headers=auth_headers(make_user(practice_row, "assistant")))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["today"] == "2026-10-30"
    assert body["appointments"]["byStatus"] == {
        "requested": 1, "scheduled": 1, "confirmed": 1, "arrived": 1, "in_treatment": 1, "done": 1, "no_show": 1,
        "cancelled": 1,
    }
    assert body["appointments"]["total"] == 7  # cancelled ones do not count
    assert [a["id"] for a in body["upcoming"]] == [up2.id, up1.id]
    assert [a["id"] for a in body["onlineRequests"]] == [request_today.id, request_later.id]
    assert body["onlineRequestsCount"] == 2
    assert body["queue"] == {"waiting": 2, "called": 1, "inTreatment": 1}
    assert body["cashTodayMillimes"] == 80_000
    assert body["remindersPending"] == 1
    assert body["dueTotalMillimes"] == 85_000
    assert body["patientsCount"] == 10


def test_dashboard_upcoming_is_limited_to_five(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    auth_headers: Factory,
) -> None:
    practice_row = make_practice()
    for i in range(7):
        make_appointment(make_patient(practice_row), starts_at=T0 + timedelta(hours=1, minutes=30 * i))
    body = client.get("/api/dashboard", headers=auth_headers(make_user(practice_row, "owner"))).json()
    assert len(body["upcoming"]) == 5


def test_dashboard_is_per_practice(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_payment: Factory, auth_headers: Factory,
) -> None:
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    make_appointment(stranger, status="requested", source="online")
    make_payment(stranger, 9_000)
    body = client.get("/api/dashboard", headers=auth_headers(make_user(mine, "dentist"))).json()
    assert (body["appointments"]["total"], body["onlineRequestsCount"], body["cashTodayMillimes"], body["patientsCount"]) == (0, 0, 0, 0)
    assert body["upcoming"] == [] and body["onlineRequests"] == []


def test_dashboard_needs_staff(client: TestClient, make_user: Factory, auth_headers: Factory) -> None:
    assert_problem(client.get("/api/dashboard"), 401, "unauthorized")
    assert_problem(client.get("/api/dashboard", headers=auth_headers(make_user(role="admin"))), 403, "forbidden")


# --- badges ----------------------------------------------------------------------------------------------------

def test_badges_count_open_requests_and_overdue_appointments(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    auth_headers: Factory, clock: Any,
) -> None:
    clock.set(at(11, 0))
    practice_row, other = make_practice(practitioners=2), make_practice()
    d1, d2 = (p.id for p in practice_row.practitioners)
    pats = [make_patient(practice_row) for _ in range(8)]
    make_appointment(pats[0], starts_at=at(9, 0), status="scheduled")  # ended 10:30 ago → overdue
    make_appointment(pats[1], starts_at=at(10, 0), duration_min=30, status="confirmed", practitioner_id=d1)  # ended 10:30 → overdue
    make_appointment(pats[2], starts_at=at(10, 0), duration_min=50, status="confirmed", practitioner_id=d2)  # ended 10:50 → not yet (15 min)
    make_appointment(pats[3], starts_at=at(8, 0), status="done")
    make_appointment(pats[4], starts_at=at(9, 0, day=29), status="scheduled")  # yesterday: not today's closing
    make_appointment(pats[5], starts_at=at(14, 0), status="requested", source="online")
    make_appointment(pats[6], starts_at=at(9, 0, day=3, month=11), status="requested", source="online")
    make_appointment(pats[7], starts_at=at(7, 0), status="requested", source="online")  # past request
    make_appointment(make_patient(other), starts_at=at(14, 0), status="requested", source="online")
    res = client.get("/api/badges", headers=auth_headers(make_user(practice_row, "assistant")))
    assert res.status_code == 200, res.text
    assert res.json() == {"onlineRequests": 2, "overdue": 2, "stockToOrder": 0}
    assert_problem(client.get("/api/badges"), 401, "unauthorized")


# --- statistics ------------------------------------------------------------------------------------------------

def test_monthly_statistics_with_previous_month(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_payment: Factory, make_service: Factory, auth_headers: Factory,
) -> None:
    practice_row = make_practice()
    owner = make_user(practice_row, "owner")
    consult = make_service(practice_row, "Consultation", 20)
    control = make_service(practice_row, "Contrôle", 15)
    old = make_patient(practice_row, created_at=at(10, day=15, month=9))
    new1 = make_patient(practice_row, created_at=at(10, day=1, month=10))
    new2 = make_patient(practice_row, created_at=datetime(2026, 10, 30, 23, 30, tzinfo=UTC))  # 31.10 00:30 Tunis
    make_patient(practice_row, created_at=at(10, day=1, month=11))
    # October (Tunis): first instant is 30.09 23:00 UTC
    make_appointment(old, starts_at=datetime(2026, 9, 30, 23, 0, tzinfo=UTC), status="done", service_id=consult.id)
    make_appointment(old, starts_at=at(9, day=5), status="done", service_id=consult.id)
    make_appointment(new1, starts_at=at(9, day=6), status="no_show", service_id=control.id)
    make_appointment(new1, starts_at=at(9, day=7), status="cancelled", service_id=control.id)
    make_appointment(new2, starts_at=at(9, day=8), status="done", service_id=control.id, source="online")
    make_appointment(new2, starts_at=at(9, day=9), status="requested", service_id=consult.id, source="online")
    make_appointment(new2, starts_at=datetime(2026, 10, 31, 23, 0, tzinfo=UTC), status="done")  # 1.11 Tunis
    # September
    make_appointment(old, starts_at=at(9, day=10, month=9), status="no_show")
    make_appointment(old, starts_at=at(9, day=11, month=9), status="no_show")
    make_appointment(old, starts_at=at(9, day=12, month=9), status="done", service_id=control.id)
    make_payment(old, 40_000, paid_at=at(9, day=5))
    make_payment(new1, 15_500, paid_at=datetime(2026, 10, 31, 22, 59, tzinfo=UTC))
    make_payment(new1, 99_000, paid_at=datetime(2026, 9, 30, 22, 59, tzinfo=UTC))  # 30.09 Tunis

    res = client.get("/api/stats?month=2026-10", headers=auth_headers(owner))
    assert res.status_code == 200, res.text
    assert res.json() == {
        "month": "2026-10",
        "appointments": {"total": 6, "done": 3, "noShow": 1, "cancelled": 1, "online": 2},
        "noShowRate": 0.25,
        "revenueMillimes": 55_500,
        "newPatients": 2,
        "topServices": [{"name": "Consultation", "count": 3}, {"name": "Contrôle", "count": 2}],
        "previous": {
            "month": "2026-09",
            "appointments": {"total": 3, "done": 1, "noShow": 2, "cancelled": 0, "online": 0},
            "noShowRate": 0.6667,
            "revenueMillimes": 99_000,
            "newPatients": 1,
            "topServices": [{"name": "Contrôle", "count": 1}],
        },
    }


def test_statistics_default_to_the_current_month_and_handle_january(
    client: TestClient, make_user: Factory, auth_headers: Factory, clock: Any
) -> None:
    owner = make_user(role="owner")
    body = client.get("/api/stats", headers=auth_headers(owner)).json()
    assert (body["month"], body["previous"]["month"], body["noShowRate"]) == ("2026-10", "2026-09", 0.0)
    assert body["appointments"] == {"total": 0, "done": 0, "noShow": 0, "cancelled": 0, "online": 0}
    assert client.get("/api/stats?month=2027-01", headers=auth_headers(owner)).json()["previous"]["month"] == "2026-12"


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "26-10", "2026-10-01", "abcd-ef"])
def test_statistics_validate_the_month(client: TestClient, make_user: Factory, auth_headers: Factory, month: str) -> None:
    assert_problem(client.get(f"/api/stats?month={month}", headers=auth_headers(make_user(role="owner"))), 422, "validation")


def test_statistics_are_for_the_owner(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    practice_row = make_practice()
    for role in ("dentist", "assistant"):
        assert_problem(client.get("/api/stats", headers=auth_headers(make_user(practice_row, role))), 403, "forbidden")
    assert_problem(client.get("/api/stats"), 401, "unauthorized")


def test_statistics_are_per_practice(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_payment: Factory, auth_headers: Factory,
) -> None:
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    make_appointment(stranger, status="done")
    make_payment(stranger, 10_000)
    body = client.get("/api/stats", headers=auth_headers(make_user(mine, "owner"))).json()
    assert (body["appointments"]["total"], body["revenueMillimes"], body["newPatients"]) == (0, 0, 0)
