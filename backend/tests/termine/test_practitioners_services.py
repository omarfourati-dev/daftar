"""CRUD ``/api/practitioners`` (people who treat – not accounts) and ``/api/services`` (the catalog)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.tables import appointment
from tests.helpers import assert_problem
from tests.termine.conftest import Factory

# --- practitioners ----------------------------------------------------------------------------------------------


def test_list_practitioners_in_order(client: TestClient, make_practice: Factory, make_practitioner: Factory, as_user: Factory) -> None:
    p = make_practice()
    make_practitioner(p, "Dr. Zied", sort=2)
    make_practitioner(p, "Dr. Amira", sort=1, title="Pr.", specialty="pediatre", color="#be123c", online_bookable=False)
    make_practitioner(p, "Dr. Ancien", sort=3, active=False)
    make_practitioner(make_practice(), "Dr. Autre cabinet")
    for role in ("owner", "dentist", "assistant"):
        res = client.get("/api/practitioners", headers=as_user(p, role))
        assert res.status_code == 200, res.text
    items = res.json()
    assert [d["name"] for d in items] == ["Dr. Amira", "Dr. Zied", "Dr. Ancien"]
    assert items[0] == {
        "id": items[0]["id"], "name": "Dr. Amira", "title": "Pr.", "specialty": "pediatre", "color": "#be123c",
        "userId": None, "onlineBookable": False, "active": True, "sort": 1,
    }
    assert items[2]["active"] is False


def test_owner_creates_a_practitioner_with_defaults(client: TestClient, make_practice: Factory, make_practitioner: Factory, as_user: Factory) -> None:
    p = make_practice()
    make_practitioner(p, "Dr. Premier", sort=4)
    res = client.post("/api/practitioners", json={"name": "  Dr. Karim  "}, headers=as_user(p, "owner"))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Dr. Karim" and body["title"] == "Dr." and body["color"] == "#0f766e"
    assert (body["onlineBookable"], body["active"], body["sort"], body["specialty"], body["userId"]) == (True, True, 5, None, None)


def test_a_practitioner_can_be_linked_to_an_account_of_the_practice(
    client: TestClient, make_practice: Factory, make_user: Factory, as_user: Factory
) -> None:
    p = make_practice()
    dentist = make_user(p, "dentist")
    stranger = make_user(make_practice(), "dentist")
    owner = as_user(p, "owner")
    res = client.post("/api/practitioners", json={"name": "Dr. Lié", "userId": dentist.id, "color": "#1D4ED8"}, headers=owner)
    assert res.status_code == 201, res.text
    assert res.json()["userId"] == dentist.id and res.json()["color"] == "#1d4ed8"
    assert_problem(client.post("/api/practitioners", json={"name": "X", "userId": stranger.id}, headers=owner), 422, "invalid_user")
    assert_problem(client.post("/api/practitioners", json={"name": "X", "userId": 999999}, headers=owner), 422, "invalid_user")


@pytest.mark.parametrize(
    "body",
    [{}, {"name": ""}, {"name": "x" * 121}, {"name": "X", "title": "x" * 21}, {"name": "X", "color": "red"},
     {"name": "X", "specialty": "sorcier"}, {"name": "X", "sort": "a"}, {"name": "X", "active": "oui"}],
)
def test_practitioner_validation(client: TestClient, make_practice: Factory, as_user: Factory, body: dict[str, Any]) -> None:
    assert_problem(client.post("/api/practitioners", json=body, headers=as_user(make_practice(), "owner")), 422, "validation")


def test_owner_updates_a_practitioner(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice(practitioners=["Dr. A"])
    doc = p.practitioners[0]
    res = client.patch(f"/api/practitioners/{doc.id}", json={"active": False, "onlineBookable": False, "title": ""},
                       headers=as_user(p, "owner"))
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["name"], body["active"], body["onlineBookable"], body["title"]) == ("Dr. A", False, False, "")
    res = client.patch(f"/api/practitioners/{doc.id}", json={"specialty": None}, headers=as_user(p, "owner"))
    assert res.json()["specialty"] is None
    assert_problem(client.patch(f"/api/practitioners/{doc.id}", json={"name": None}, headers=as_user(p, "owner")), 422, "validation")


def test_delete_an_unused_practitioner(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice(practitioners=2)
    owner = as_user(p, "owner")
    assert client.delete(f"/api/practitioners/{p.practitioners[0].id}", headers=owner).status_code == 204
    assert [d["id"] for d in client.get("/api/practitioners", headers=owner).json()] == [p.practitioners[1].id]
    assert_problem(client.delete(f"/api/practitioners/{p.practitioners[0].id}", headers=owner), 404, "not_found")


def test_a_practitioner_with_appointments_is_deactivated_not_deleted(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory, clock: Any, db: Any
) -> None:
    p = make_practice(practitioners=1)
    doc = p.practitioners[0]
    make_appointment(make_patient(p), practitioner_id=doc.id, starts_at=clock.now() - timedelta(days=30), status="done")
    assert_problem(client.delete(f"/api/practitioners/{doc.id}", headers=as_user(p, "owner")), 409, "practitioner_in_use")
    with db.connect() as conn:
        assert conn.execute(select(appointment.c.practitioner_id)).scalar_one() == doc.id


def test_practitioners_of_another_practice_are_404(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    other = make_practice(practitioners=1).practitioners[0]
    owner = as_user(make_practice(), "owner")
    assert_problem(client.patch(f"/api/practitioners/{other.id}", json={"name": "X"}, headers=owner), 404, "not_found")
    assert_problem(client.delete(f"/api/practitioners/{other.id}", headers=owner), 404, "not_found")


@pytest.mark.parametrize("role", ["dentist", "assistant"])
def test_only_the_owner_manages_practitioners(client: TestClient, make_practice: Factory, as_user: Factory, role: str) -> None:
    p = make_practice(practitioners=1)
    h = as_user(p, role)
    doc = p.practitioners[0].id
    assert_problem(client.post("/api/practitioners", json={"name": "X"}, headers=h), 403, "forbidden")
    assert_problem(client.patch(f"/api/practitioners/{doc}", json={"name": "X"}, headers=h), 403, "forbidden")
    assert_problem(client.delete(f"/api/practitioners/{doc}", headers=h), 403, "forbidden")


def test_practitioners_need_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    assert_problem(client.get("/api/practitioners"), 401, "unauthorized")
    assert_problem(client.post("/api/practitioners", json={"name": "X"}), 401, "unauthorized")
    p = make_practice(status="suspended", practitioners=1)
    owner = as_user(p, "owner")
    doc = p.practitioners[0].id
    assert client.get("/api/practitioners", headers=owner).status_code == 200
    assert_problem(client.post("/api/practitioners", json={"name": "X"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.patch(f"/api/practitioners/{doc}", json={"name": "X"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/practitioners/{doc}", headers=owner), 402, "subscription_suspended")


# --- services ---------------------------------------------------------------------------------------------------


def test_list_services_in_order(client: TestClient, make_practice: Factory, make_service: Factory, as_user: Factory) -> None:
    p = make_practice()
    make_service(p, "Détartrage", 45, sort=2, price_millimes=60_000, online_bookable=True, name_ar="إزالة الجير")
    make_service(p, "Consultation", 30, sort=1, color="#0369a1")
    make_service(make_practice(), "Autre cabinet", 30)
    for role in ("owner", "dentist", "assistant"):
        res = client.get("/api/services", headers=as_user(p, role))
        assert res.status_code == 200, res.text
    items = res.json()
    assert [s["nameFr"] for s in items] == ["Consultation", "Détartrage"]
    assert items[1] == {
        "id": items[1]["id"], "nameFr": "Détartrage", "nameAr": "إزالة الجير", "durationMin": 45, "priceMillimes": 60_000,
        "onlineBookable": True, "color": None, "active": True, "sort": 2,
    }


def test_owner_creates_updates_and_deletes_a_service(
    client: TestClient, make_practice: Factory, make_service: Factory, make_patient: Factory, make_appointment: Factory,
    as_user: Factory, db: Any
) -> None:
    p = make_practice()
    make_service(p, "Consultation", 30, sort=3)
    owner = as_user(p, "owner")
    res = client.post("/api/services", json={"nameFr": "Bilan", "durationMin": 60}, headers=owner)
    assert res.status_code == 201, res.text
    created = res.json()
    assert (created["nameAr"], created["priceMillimes"], created["onlineBookable"], created["color"], created["sort"]) == (
        "", None, False, None, 4)
    res = client.patch(f"/api/services/{created['id']}", json={"priceMillimes": 45_000, "onlineBookable": True,
                                                              "color": "#B45309"}, headers=owner)
    assert res.status_code == 200, res.text
    assert (res.json()["priceMillimes"], res.json()["onlineBookable"], res.json()["color"]) == (45_000, True, "#b45309")
    assert client.patch(f"/api/services/{created['id']}", json={"priceMillimes": None}, headers=owner).json()["priceMillimes"] is None
    booked = make_appointment(make_patient(p), service_id=created["id"])
    assert client.delete(f"/api/services/{created['id']}", headers=owner).status_code == 204
    with db.connect() as conn:  # the appointment stays, without its service
        assert conn.execute(select(appointment.c.service_id).where(appointment.c.id == booked.id)).scalar_one() is None
    assert_problem(client.delete(f"/api/services/{created['id']}", headers=owner), 404, "not_found")


@pytest.mark.parametrize(
    "body",
    [{"durationMin": 30}, {"nameFr": "", "durationMin": 30}, {"nameFr": "X"}, {"nameFr": "X", "durationMin": 4},
     {"nameFr": "X", "durationMin": 481}, {"nameFr": "X", "durationMin": 30, "priceMillimes": -1},
     {"nameFr": "X", "durationMin": 30, "priceMillimes": 12.5}, {"nameFr": "X", "durationMin": 30, "color": "bleu"},
     {"nameFr": "X", "durationMin": 30, "nameAr": "x" * 121}],
)
def test_service_validation(client: TestClient, make_practice: Factory, as_user: Factory, body: dict[str, Any]) -> None:
    assert_problem(client.post("/api/services", json=body, headers=as_user(make_practice(), "owner")), 422, "validation")


def test_services_of_another_practice_are_404(client: TestClient, make_practice: Factory, make_service: Factory, as_user: Factory) -> None:
    other = make_service(make_practice())
    owner = as_user(make_practice(), "owner")
    assert_problem(client.patch(f"/api/services/{other.id}", json={"nameFr": "X"}, headers=owner), 404, "not_found")
    assert_problem(client.delete(f"/api/services/{other.id}", headers=owner), 404, "not_found")


@pytest.mark.parametrize("role", ["dentist", "assistant"])
def test_only_the_owner_manages_services(client: TestClient, make_practice: Factory, make_service: Factory, as_user: Factory, role: str) -> None:
    p = make_practice()
    s = make_service(p)
    h = as_user(p, role)
    assert_problem(client.post("/api/services", json={"nameFr": "X", "durationMin": 30}, headers=h), 403, "forbidden")
    assert_problem(client.patch(f"/api/services/{s.id}", json={"nameFr": "X"}, headers=h), 403, "forbidden")
    assert_problem(client.delete(f"/api/services/{s.id}", headers=h), 403, "forbidden")


def test_services_need_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, make_service: Factory, as_user: Factory) -> None:
    assert_problem(client.get("/api/services"), 401, "unauthorized")
    p = make_practice(status="suspended")
    s = make_service(p)
    owner = as_user(p, "owner")
    assert client.get("/api/services", headers=owner).status_code == 200
    assert_problem(client.post("/api/services", json={"nameFr": "X", "durationMin": 30}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.patch(f"/api/services/{s.id}", json={"nameFr": "X"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/services/{s.id}", headers=owner), 402, "subscription_suspended")
