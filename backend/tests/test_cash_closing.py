"""Cash closing of a day and its verification by the owner (section 16.3)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def setup(make_practice: Factory, make_user: Factory, make_patient: Factory, make_payment: Factory) -> Any:
    p = make_practice()
    owner = make_user(p, "owner", name="Dr. Owner")
    sonia = make_user(p, "assistant", name="Sonia")
    pat = make_patient(p)
    make_payment(pat, 40_000, method="cash", paid_at=T0)
    make_payment(pat, 15_500, method="cash", paid_at=datetime(2026, 10, 30, 22, 59, tzinfo=UTC))  # 23:59 Tunis
    make_payment(pat, 30_000, method="card", paid_at=T0)  # not in the drawer
    make_payment(pat, 99_000, method="cash", paid_at=T0 - timedelta(days=1))  # yesterday
    make_payment(make_patient(make_practice()), 77_000, method="cash", paid_at=T0)  # another practice
    return type("S", (), {"practice": p, "owner": owner, "sonia": sonia, "patient": pat})


def close(client: TestClient, headers: dict[str, str], day: str = "2026-10-30", counted: Any = 50_000, **extra: Any) -> Any:
    return client.post("/api/cash/close", json={"day": day, "countedCashMillimes": counted, **extra}, headers=headers)


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_staff_close_the_day_against_the_cash_payments(client: TestClient, setup: Any, make_user: Factory,
                                                       auth_headers: Factory, role: str) -> None:
    user = make_user(setup.practice, role, name="Caisse")
    res = close(client, auth_headers(user), counted=55_000, note=" Billet de 0,500 manquant ")
    assert res.status_code == 200, res.text
    assert res.json() == {
        "day": "2026-10-30", "expectedCashMillimes": 55_500, "countedCashMillimes": 55_000, "differenceMillimes": -500,
        "note": "Billet de 0,500 manquant", "closedBy": "Caisse", "closedAt": "2026-10-30T09:00:00+01:00",
        "verifiedBy": None, "verifiedAt": None, "stale": False,
    }


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"day": "2026-10-30", "countedCashMillimes": 12.5}, "validation"),
        ({"day": "2026-10-30", "countedCashMillimes": "50000"}, "validation"),
        ({"day": "2026-10-30", "countedCashMillimes": -1}, "validation"),
        ({"day": "2026-10-30", "countedCashMillimes": 100_000_001}, "validation"),
        ({"countedCashMillimes": 0}, "validation"),
        ({"day": "30/10/2026", "countedCashMillimes": 0}, "validation"),
        ({"day": "2026-10-30", "countedCashMillimes": 0, "note": "x" * 501}, "validation"),
        ({"day": "2026-10-31", "countedCashMillimes": 0}, "day_in_future"),
    ],
)
def test_close_validation(client: TestClient, setup: Any, auth_headers: Factory, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/cash/close", json=body, headers=auth_headers(setup.sonia)), 422, code)


def test_an_empty_drawer_can_be_closed(client: TestClient, setup: Any, auth_headers: Factory) -> None:
    body = close(client, auth_headers(setup.sonia), day="2026-10-28", counted=0).json()
    assert (body["expectedCashMillimes"], body["differenceMillimes"]) == (0, 0)


def test_closing_again_recounts_until_the_owner_verified(client: TestClient, setup: Any, auth_headers: Factory, clock: Any) -> None:
    close(client, auth_headers(setup.sonia), counted=50_000)
    clock.advance(minutes=30)
    again = close(client, auth_headers(setup.owner), counted=55_500).json()
    assert (again["countedCashMillimes"], again["differenceMillimes"], again["closedBy"], again["closedAt"]) == (
        55_500, 0, "Dr. Owner", "2026-10-30T09:30:00+01:00")
    res = client.post("/api/cash/2026-10-30/verify", headers=auth_headers(setup.owner))
    assert res.status_code == 200, res.text
    assert (res.json()["verifiedBy"], res.json()["verifiedAt"]) == ("Dr. Owner", "2026-10-30T09:30:00+01:00")
    assert_problem(close(client, auth_headers(setup.sonia)), 409, "cash_day_verified")
    assert_problem(client.post("/api/cash/2026-10-30/verify", headers=auth_headers(setup.owner)), 409, "cash_day_verified")


def test_verify_is_for_the_owner_of_this_practice(client: TestClient, setup: Any, make_user: Factory,
                                                  auth_headers: Factory) -> None:
    assert_problem(client.post("/api/cash/2026-10-30/verify", headers=auth_headers(setup.owner)), 404, "not_found")
    close(client, auth_headers(setup.sonia))
    for role in ("dentist", "assistant"):
        assert_problem(client.post("/api/cash/2026-10-30/verify", headers=auth_headers(make_user(setup.practice, role))),
                       403, "forbidden")
    stranger = make_user(role="owner")
    assert_problem(client.post("/api/cash/2026-10-30/verify", headers=auth_headers(stranger)), 404, "not_found")
    assert_problem(client.post("/api/cash/30-10-2026/verify", headers=auth_headers(setup.owner)), 422, "validation")
    assert_problem(client.post("/api/cash/2026-10-30/verify"), 401, "unauthorized")


def test_a_suspended_subscription_blocks_closing_and_verifying(client: TestClient, make_practice: Factory,
                                                               make_user: Factory, auth_headers: Factory) -> None:
    owner = make_user(make_practice(status="suspended"), "owner")
    assert_problem(close(client, auth_headers(owner)), 402, "subscription_suspended")
    assert_problem(client.post("/api/cash/2026-10-30/verify", headers=auth_headers(owner)), 402, "subscription_suspended")


def test_cash_of_the_day_carries_the_closing(client: TestClient, setup: Any, make_payment: Factory, auth_headers: Factory) -> None:
    h = auth_headers(setup.sonia)
    assert client.get("/api/cash", headers=h).json()["closing"] is None
    close(client, h, counted=55_500)
    closing = client.get("/api/cash?day=2026-10-30", headers=h).json()["closing"]
    assert (closing["expectedCashMillimes"], closing["differenceMillimes"], closing["stale"]) == (55_500, 0, False)
    make_payment(setup.patient, 5_000, method="cash", paid_at=T0 + timedelta(minutes=1))  # cashed after the closing
    assert client.get("/api/cash", headers=h).json()["closing"]["stale"] is True
    assert client.get("/api/cash?day=2026-10-29", headers=h).json()["closing"] is None


def test_the_owner_dashboard_lists_unverified_days(client: TestClient, setup: Any, auth_headers: Factory) -> None:
    close(client, auth_headers(setup.sonia), day="2026-10-28", counted=0)
    close(client, auth_headers(setup.sonia), day="2026-10-29", counted=98_000)
    close(client, auth_headers(setup.sonia), day="2026-10-30", counted=55_500)
    client.post("/api/cash/2026-10-28/verify", headers=auth_headers(setup.owner))
    days = client.get("/api/dashboard", headers=auth_headers(setup.owner)).json()["unverifiedCashDays"]
    assert days == [
        {"day": "2026-10-30", "differenceMillimes": 0, "closedBy": "Sonia"},
        {"day": "2026-10-29", "differenceMillimes": -1_000, "closedBy": "Sonia"},
    ]
    assert client.get("/api/dashboard", headers=auth_headers(setup.sonia)).json()["unverifiedCashDays"] == []
