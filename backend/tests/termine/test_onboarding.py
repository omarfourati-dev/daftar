"""“Erste Schritte” (backlog A5, section 15): ``GET /api/onboarding``, ``POST /api/onboarding/{key}/done``, ``/dismiss``."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from daftar.tables import import_job
from tests.helpers import assert_problem
from tests.termine.conftest import Factory

KEYS = ["hours", "services", "practitioners", "team", "booking", "import", "install", "poster"]


def steps(client: TestClient, headers: dict[str, str]) -> dict[str, bool]:
    res = client.get("/api/onboarding", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [s["key"] for s in body["steps"]] == KEYS
    return {s["key"]: s["done"] for s in body["steps"]}


def test_a_new_practice_has_everything_to_do(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    assert steps(client, owner) == dict.fromkeys(KEYS, False)
    assert client.get("/api/onboarding", headers=owner).json()["dismissed"] is False
    for role in ("dentist", "assistant"):  # every role reads it (and their accounts tick "team")
        assert steps(client, as_user(p, role))["team"] is True


def test_steps_follow_the_data(
    client: TestClient, make_practice: Factory, make_service: Factory, make_practitioner: Factory, make_user: Factory,
    as_user: Factory, make_invitation: Factory, db: Any, clock: Any,
) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    make_service(p, price_millimes=None)
    make_service(p, price_millimes=50_000, active=False)
    make_practitioner(p, active=False)
    make_user(p, "owner")
    assert not any(steps(client, owner).values())  # a price only on an inactive service, an inactive practitioner
    make_service(p, price_millimes=40_000)
    make_practitioner(p)
    client.patch("/api/practice", json={"weeklyHours": {"1": [["09:00", "17:00"]]}, "onlineBooking": {"enabled": True}}, headers=owner)
    done = steps(client, owner)
    assert done == {**dict.fromkeys(KEYS, False), "services": True, "practitioners": True, "hours": True, "booking": True}
    make_invitation(p, "assistant")
    assert steps(client, owner)["team"] is True
    with db.begin() as conn:
        conn.execute(insert(import_job).values(practice_id=p.id, filename="patients.xlsx", file_bytes=b"x",
                                               created_at=clock.now(), expires_at=clock.now() + timedelta(days=1),
                                               committed_at=clock.now()))
    assert steps(client, owner)["import"] is True


def test_saving_the_default_hours_counts_as_done(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    owner = as_user(p, "owner")
    current = client.get("/api/practice", headers=owner).json()["weeklyHours"]
    client.patch("/api/practice", json={"weeklyHours": current}, headers=owner)
    assert steps(client, owner)["hours"] is True


def test_changed_hours_count_without_saving_them_here(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice(weekly_hours={"1": [["10:00", "16:00"]]})
    assert steps(client, as_user(p, "owner"))["hours"] is True


def test_hours_given_by_the_admin_count(client: TestClient, as_user: Factory, make_user: Factory, auth_headers: Factory) -> None:
    body = {"name": "Cabinet A", "slug": "cabinet-a", "specialty": "autre", "contactName": "Dr A", "phone": "20123456",
            "address": "Rue 1", "city": "Tunis", "governorate": "tunis",
            "weeklyHours": {str(d): [["08:00", "12:30"], ["14:00", "18:00"]] for d in range(1, 7)}}
    created = client.post("/api/admin/practices", json=body, headers=as_user(role="admin")).json()["practice"]
    owner = auth_headers(make_user(type("P", (), {"id": created["id"]})(), "owner"))
    assert steps(client, owner)["hours"] is True
    without = client.post("/api/admin/practices", json={**body, "slug": "cabinet-b", "weeklyHours": None},
                          headers=as_user(role="admin")).json()["practice"]
    assert steps(client, auth_headers(make_user(type("P", (), {"id": without["id"]})(), "owner")))["hours"] is False


@pytest.mark.parametrize("key", ["install", "poster", "import"])
def test_marking_a_manual_step_done(client: TestClient, make_practice: Factory, as_user: Factory, key: str) -> None:
    p = make_practice()
    res = client.post(f"/api/onboarding/{key}/done", headers=as_user(p, "assistant"))
    assert res.status_code == 200, res.text
    assert {s["key"]: s["done"] for s in res.json()["steps"]}[key] is True
    assert steps(client, as_user(p, "owner"))[key] is True
    assert steps(client, as_user(make_practice(), "owner"))[key] is False  # another practice


@pytest.mark.parametrize("key", ["hours", "services", "practitioners", "team", "booking"])
def test_derived_steps_cannot_be_ticked_by_hand(client: TestClient, make_practice: Factory, as_user: Factory, key: str) -> None:
    assert_problem(client.post(f"/api/onboarding/{key}/done", headers=as_user(make_practice(), "owner")), 422, "onboarding_derived")


def test_unknown_step(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    assert_problem(client.post("/api/onboarding/coffee/done", headers=as_user(make_practice(), "owner")), 422, "validation")


def test_dismiss_the_checklist(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice()
    client.post("/api/onboarding/install/done", headers=as_user(p, "owner"))
    res = client.post("/api/onboarding/dismiss", headers=as_user(p, "owner"))
    assert res.status_code == 200, res.text
    assert res.json()["dismissed"] is True
    assert client.get("/api/onboarding", headers=as_user(p, "dentist")).json()["dismissed"] is True
    assert steps(client, as_user(p, "owner"))["install"] is True  # dismissing keeps what was done


def test_onboarding_needs_a_token_a_practice_and_an_active_subscription(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    assert_problem(client.get("/api/onboarding"), 401, "unauthorized")
    assert_problem(client.post("/api/onboarding/dismiss"), 401, "unauthorized")
    assert_problem(client.get("/api/onboarding", headers=as_user(role="admin")), 403, "forbidden")
    owner = as_user(make_practice(status="suspended"), "owner")
    assert client.get("/api/onboarding", headers=owner).status_code == 200
    assert_problem(client.post("/api/onboarding/install/done", headers=owner), 402, "subscription_suspended")
    assert_problem(client.post("/api/onboarding/dismiss", headers=owner), 402, "subscription_suspended")
