"""CRUD ``/api/closures`` – holidays and closing days (no appointments, no online bookings)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem
from tests.termine.conftest import MON, SAT, TUE, Factory, at


def test_owner_creates_a_closure_and_staff_lists_them(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    res = client.post("/api/closures", json={"startsOn": "2026-12-24", "endsOn": "2026-12-31", "label": "Congés"}, headers=owner)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {"id": body["id"], "startsOn": "2026-12-24", "endsOn": "2026-12-31", "label": "Congés", "affectedAppointments": 0}
    single = client.post("/api/closures", json={"startsOn": "2026-11-07"}, headers=owner).json()
    assert (single["endsOn"], single["label"]) == ("2026-11-07", "")
    for role in ("owner", "dentist", "assistant"):
        res = client.get("/api/closures", headers=as_user(p, role))
        assert res.status_code == 200, res.text
    assert [c["startsOn"] for c in res.json()] == ["2026-11-07", "2026-12-24"]
    assert {k for k in res.json()[0]} == {"id", "startsOn", "endsOn", "label"}


def test_list_closures_overlapping_a_range(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    for start, end in (("2026-10-01", "2026-10-05"), ("2026-10-28", "2026-11-03"), ("2026-12-01", "2026-12-01")):
        client.post("/api/closures", json={"startsOn": start, "endsOn": end}, headers=owner)
    res = client.get("/api/closures?from=2026-11-01&to=2026-11-30", headers=owner)
    assert [c["startsOn"] for c in res.json()] == ["2026-10-28"]
    res = client.get("/api/closures?from=2026-10-05", headers=owner)
    assert [c["startsOn"] for c in res.json()] == ["2026-10-01", "2026-10-28", "2026-12-01"]


def test_creating_a_closure_counts_the_appointments_already_booked(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice()
    make_appointment(make_patient(p), starts_at=at(MON, "09:00"))
    make_appointment(make_patient(p), starts_at=at(TUE, "23:30"))  # late evening, still Tuesday in Tunis
    make_appointment(make_patient(p), starts_at=at(MON, "10:00"), status="cancelled")
    make_appointment(make_patient(p), starts_at=at(SAT, "11:00"))
    res = client.post("/api/closures", json={"startsOn": MON.isoformat(), "endsOn": TUE.isoformat()}, headers=as_user(p, "owner"))
    assert res.json()["affectedAppointments"] == 2


def test_update_and_delete_a_closure(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    made = client.post("/api/closures", json={"startsOn": "2027-01-01"}, headers=owner).json()
    res = client.patch(f"/api/closures/{made['id']}", json={"endsOn": "2027-01-02", "label": "Nouvel an"}, headers=owner)
    assert res.status_code == 200, res.text
    assert (res.json()["startsOn"], res.json()["endsOn"], res.json()["label"]) == ("2027-01-01", "2027-01-02", "Nouvel an")
    assert_problem(client.patch(f"/api/closures/{made['id']}", json={"endsOn": "2026-12-31"}, headers=owner), 422, "invalid_range")
    assert client.delete(f"/api/closures/{made['id']}", headers=owner).status_code == 204
    assert client.get("/api/closures", headers=owner).json() == []
    assert_problem(client.delete(f"/api/closures/{made['id']}", headers=owner), 404, "not_found")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "validation"),
        ({"startsOn": "31/12/2026"}, "validation"),
        ({"startsOn": "2026-12-31", "endsOn": "2026-12-30"}, "invalid_range"),
        ({"startsOn": "2026-01-01", "endsOn": "2027-01-03"}, "invalid_range"),  # more than a year
        ({"startsOn": "2026-12-31", "label": "x" * 121}, "validation"),
    ],
)
def test_closure_validation(client: TestClient, make_practice: Factory, as_user: Factory, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/closures", json=body, headers=as_user(make_practice(), "owner")), 422, code)


def test_closures_of_another_practice_are_invisible(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    other = client.post("/api/closures", json={"startsOn": "2026-12-01"}, headers=as_user(make_practice(), "owner")).json()
    owner = as_user(make_practice(), "owner")
    assert client.get("/api/closures", headers=owner).json() == []
    assert_problem(client.patch(f"/api/closures/{other['id']}", json={"label": "X"}, headers=owner), 404, "not_found")
    assert_problem(client.delete(f"/api/closures/{other['id']}", headers=owner), 404, "not_found")


@pytest.mark.parametrize("role", ["dentist", "assistant"])
def test_only_the_owner_manages_closures(client: TestClient, make_practice: Factory, as_user: Factory, role: str) -> None:
    p = make_practice()
    made = client.post("/api/closures", json={"startsOn": "2026-12-01"}, headers=as_user(p, "owner")).json()
    h = as_user(p, role)
    assert_problem(client.post("/api/closures", json={"startsOn": "2026-12-02"}, headers=h), 403, "forbidden")
    assert_problem(client.patch(f"/api/closures/{made['id']}", json={"label": "X"}, headers=h), 403, "forbidden")
    assert_problem(client.delete(f"/api/closures/{made['id']}", headers=h), 403, "forbidden")


def test_closures_need_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, as_user: Factory, db: Any) -> None:
    assert_problem(client.get("/api/closures"), 401, "unauthorized")
    p = make_practice()
    owner = as_user(p, "owner")
    made = client.post("/api/closures", json={"startsOn": "2026-12-01"}, headers=owner).json()
    from sqlalchemy import update

    from daftar.tables import practice

    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == p.id).values(status="suspended"))
    assert client.get("/api/closures", headers=owner).status_code == 200
    assert_problem(client.post("/api/closures", json={"startsOn": "2026-12-02"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.patch(f"/api/closures/{made['id']}", json={"label": "X"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/closures/{made['id']}", headers=owner), 402, "subscription_suspended")


def test_dates_are_plain_days(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    body = client.post("/api/closures", json={"startsOn": date(2026, 11, 7).isoformat()}, headers=as_user(make_practice(), "owner")).json()
    assert body["startsOn"] == "2026-11-07"
