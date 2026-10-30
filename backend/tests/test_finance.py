"""Money (section 5 "Geld"): treatments, payments in instalments and deposits, receipt, cash of the day, balances."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from daftar.tables import payment, treatment
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def setup(make_practice: Factory, make_user: Factory, make_patient: Factory) -> Any:
    practice_row = make_practice("Cabinet Lac", address="Rue du Lac 3", city="Tunis", phone="71 000 000")
    owner = make_user(practice_row, "owner", name="Dr. Owner")
    pat = make_patient(practice_row, first_name="Amira", last_name="Trabelsi")
    return type("S", (), {"practice": practice_row, "owner": owner, "patient": pat})


# --- treatments ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_add_treatment(client: TestClient, setup: Any, make_user: Factory, make_appointment: Factory,
                       auth_headers: Factory, role: str) -> None:
    appt = make_appointment(setup.patient)
    res = client.post(
        f"/api/patients/{setup.patient.id}/treatments",
        json={"label": " Couronne céramique ", "tooth": "26", "priceMillimes": 450_000, "performedOn": "2026-10-30",
              "appointmentId": appt.id},
        headers=auth_headers(make_user(setup.practice, role)),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {"id": body["id"], "label": "Couronne céramique", "tooth": "26", "priceMillimes": 450_000,
                    "performedOn": "2026-10-30", "appointmentId": appt.id, "createdAt": "2026-10-30T09:00:00+01:00"}


def test_a_free_act_has_price_zero(client: TestClient, setup: Any, auth_headers: Factory) -> None:
    res = client.post(f"/api/patients/{setup.patient.id}/treatments", json={"label": "Contrôle", "priceMillimes": 0},
                      headers=auth_headers(setup.owner))
    assert res.status_code == 201 and res.json()["tooth"] is None and res.json()["performedOn"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"priceMillimes": -1},
        {"priceMillimes": 12.5},
        {"priceMillimes": "12500"},
        {"priceMillimes": True},
        {"priceMillimes": 100_000_001},
        {"priceMillimes": None},
        {"label": ""},
        {"label": "x" * 201},
        {"tooth": "x" * 21},
        {"performedOn": "30/10/2026"},
    ],
)
def test_treatment_validation(client: TestClient, setup: Any, auth_headers: Factory, change: dict[str, Any]) -> None:
    body = {"label": "Soin", "priceMillimes": 60_000, **change}
    res = client.post(f"/api/patients/{setup.patient.id}/treatments", json=body, headers=auth_headers(setup.owner))
    assert_problem(res, 422, "validation")


def test_treatment_appointment_must_belong_to_the_patient(
    client: TestClient, setup: Any, make_patient: Factory, make_practice: Factory, make_appointment: Factory,
    auth_headers: Factory,
) -> None:
    sibling = make_appointment(make_patient(setup.practice))
    foreign = make_appointment(make_patient(make_practice()))
    for appt in (sibling, foreign):
        res = client.post(f"/api/patients/{setup.patient.id}/treatments",
                          json={"label": "Soin", "priceMillimes": 1000, "appointmentId": appt.id}, headers=auth_headers(setup.owner))
        assert_problem(res, 422, "appointment_mismatch")


def test_update_and_delete_treatment(client: TestClient, setup: Any, make_treatment: Factory, auth_headers: Factory, db: Engine) -> None:
    t = make_treatment(setup.patient, 100_000, label="Soin", tooth="11")
    res = client.patch(f"/api/treatments/{t.id}", json={"priceMillimes": 80_000, "tooth": None}, headers=auth_headers(setup.owner))
    assert res.status_code == 200, res.text
    assert (res.json()["priceMillimes"], res.json()["tooth"], res.json()["label"]) == (80_000, None, "Soin")
    assert_problem(client.patch(f"/api/treatments/{t.id}", json={"priceMillimes": -5}, headers=auth_headers(setup.owner)), 422, "validation")
    assert_problem(client.patch(f"/api/treatments/{t.id}", json={"label": None}, headers=auth_headers(setup.owner)), 422, "validation")
    assert client.delete(f"/api/treatments/{t.id}", headers=auth_headers(setup.owner)).status_code == 204
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(treatment)).scalar_one() == 0


def test_treatments_of_another_practice_are_404(
    client: TestClient, setup: Any, make_practice: Factory, make_patient: Factory, make_treatment: Factory, auth_headers: Factory
) -> None:
    stranger = make_patient(make_practice())
    t = make_treatment(stranger, 1000)
    h = auth_headers(setup.owner)
    assert_problem(client.post(f"/api/patients/{stranger.id}/treatments", json={"label": "x", "priceMillimes": 1}, headers=h), 404, "not_found")
    assert_problem(client.patch(f"/api/treatments/{t.id}", json={"label": "y"}, headers=h), 404, "not_found")
    assert_problem(client.delete(f"/api/treatments/{t.id}", headers=h), 404, "not_found")


def test_treatment_writes_need_a_staff_token_and_an_active_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_treatment: Factory,
    auth_headers: Factory,
) -> None:
    practice_row = make_practice(status="suspended")
    pat = make_patient(practice_row)
    t = make_treatment(pat, 1000)
    h = auth_headers(make_user(practice_row, "assistant"))
    assert_problem(client.post(f"/api/patients/{pat.id}/treatments", json={"label": "x", "priceMillimes": 1}), 401, "unauthorized")
    assert_problem(client.post(f"/api/patients/{pat.id}/treatments", json={"label": "x", "priceMillimes": 1},
                               headers=auth_headers(make_user(role="admin"))), 403, "forbidden")
    assert_problem(client.post(f"/api/patients/{pat.id}/treatments", json={"label": "x", "priceMillimes": 1}, headers=h), 402, "subscription_suspended")
    assert_problem(client.patch(f"/api/treatments/{t.id}", json={"label": "y"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/treatments/{t.id}", headers=h), 402, "subscription_suspended")


# --- payments --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_record_an_instalment(client: TestClient, setup: Any, make_user: Factory, make_treatment: Factory,
                              auth_headers: Factory, role: str) -> None:
    make_treatment(setup.patient, 300_000)
    cashier = make_user(setup.practice, role, name="Sonia")
    res = client.post(f"/api/patients/{setup.patient.id}/payments",
                      json={"amountMillimes": 100_000, "method": "cash", "note": " 1er versement "}, headers=auth_headers(cashier))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {"id": body["id"], "patientId": setup.patient.id, "patientName": "Amira Trabelsi",
                    "amountMillimes": 100_000, "method": "cash", "paidAt": "2026-10-30T09:00:00+01:00",
                    "appointmentId": None, "isDeposit": False, "note": "1er versement", "receivedByName": "Sonia"}
    ledger = client.get(f"/api/patients/{setup.patient.id}/ledger", headers=auth_headers(cashier)).json()
    assert (ledger["totalMillimes"], ledger["paidMillimes"], ledger["dueMillimes"]) == (300_000, 100_000, 200_000)


def test_deposit_for_an_appointment(client: TestClient, setup: Any, make_appointment: Factory, auth_headers: Factory) -> None:
    appt = make_appointment(setup.patient, deposit_required_millimes=20_000)
    res = client.post(f"/api/patients/{setup.patient.id}/payments",
                      json={"amountMillimes": 20_000, "method": "d17", "appointmentId": appt.id, "isDeposit": True,
                            "paidAt": "2026-10-29T17:45:00+01:00"}, headers=auth_headers(setup.owner))
    assert res.status_code == 201, res.text
    assert (res.json()["isDeposit"], res.json()["appointmentId"], res.json()["paidAt"]) == (True, appt.id, "2026-10-29T17:45:00+01:00")
    appts = client.get(f"/api/patients/{setup.patient.id}/appointments", headers=auth_headers(setup.owner)).json()
    assert appts[0]["depositPaidMillimes"] == 20_000


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"amountMillimes": 0}, "validation"),
        ({"amountMillimes": -5000}, "validation"),
        ({"amountMillimes": 12.5}, "validation"),
        ({"amountMillimes": 12500.0}, "validation"),
        ({"amountMillimes": "12500"}, "validation"),
        ({"amountMillimes": True}, "validation"),
        ({"amountMillimes": 100_000_001}, "validation"),
        ({"method": "bitcoin"}, "validation"),
        ({"method": None}, "validation"),
        ({"note": "x" * 501}, "validation"),
        ({"paidAt": "2026-10-30T09:00:00"}, "validation"),
        ({"paidAt": "2026-10-31T09:00:00+01:00"}, "paid_at_in_future"),
        ({"isDeposit": True}, "deposit_needs_appointment"),
    ],
)
def test_payment_validation(client: TestClient, setup: Any, auth_headers: Factory, change: dict[str, Any], code: str) -> None:
    body = {"amountMillimes": 10_000, "method": "cash", **change}
    res = client.post(f"/api/patients/{setup.patient.id}/payments", json=body, headers=auth_headers(setup.owner))
    assert_problem(res, 422, code)


def test_payment_appointment_must_belong_to_the_patient(
    client: TestClient, setup: Any, make_patient: Factory, make_practice: Factory, make_appointment: Factory, auth_headers: Factory
) -> None:
    for appt in (make_appointment(make_patient(setup.practice)), make_appointment(make_patient(make_practice()))):
        res = client.post(f"/api/patients/{setup.patient.id}/payments",
                          json={"amountMillimes": 1000, "method": "cash", "appointmentId": appt.id, "isDeposit": True},
                          headers=auth_headers(setup.owner))
        assert_problem(res, 422, "appointment_mismatch")


def test_receipt_carries_the_practice(client: TestClient, setup: Any, make_payment: Factory, make_user: Factory, auth_headers: Factory) -> None:
    pay = make_payment(setup.patient, 45_500, method="card", received_by=setup.owner.id)
    res = client.get(f"/api/payments/{pay.id}", headers=auth_headers(make_user(setup.practice, "assistant")))
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["amountMillimes"], body["method"], body["receivedByName"], body["patientName"]) == (45_500, "card", "Dr. Owner", "Amira Trabelsi")
    assert body["practice"] == {"name": "Cabinet Lac", "nameAr": "", "address": "Rue du Lac 3", "city": "Tunis",
                                "phone": "71 000 000", "taxId": ""}


def test_delete_payment_is_for_the_owner(client: TestClient, setup: Any, make_payment: Factory, make_user: Factory,
                                         auth_headers: Factory, db: Engine) -> None:
    pay = make_payment(setup.patient, 10_000)
    for role in ("dentist", "assistant"):
        assert_problem(client.delete(f"/api/payments/{pay.id}", headers=auth_headers(make_user(setup.practice, role))), 403, "forbidden")
    assert client.delete(f"/api/payments/{pay.id}", headers=auth_headers(setup.owner)).status_code == 204
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(payment)).scalar_one() == 0


def test_payments_of_another_practice_are_404(
    client: TestClient, setup: Any, make_practice: Factory, make_patient: Factory, make_payment: Factory, auth_headers: Factory
) -> None:
    stranger = make_patient(make_practice())
    pay = make_payment(stranger, 1000)
    h = auth_headers(setup.owner)
    assert_problem(client.post(f"/api/patients/{stranger.id}/payments", json={"amountMillimes": 1, "method": "cash"}, headers=h), 404, "not_found")
    assert_problem(client.get(f"/api/payments/{pay.id}", headers=h), 404, "not_found")
    assert_problem(client.delete(f"/api/payments/{pay.id}", headers=h), 404, "not_found")


def test_payment_writes_need_an_active_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_payment: Factory, auth_headers: Factory
) -> None:
    practice_row = make_practice(status="suspended")
    pat = make_patient(practice_row)
    pay = make_payment(pat, 1000)
    h = auth_headers(make_user(practice_row, "owner"))
    assert_problem(client.post(f"/api/patients/{pat.id}/payments", json={"amountMillimes": 1, "method": "cash"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/payments/{pay.id}", headers=h), 402, "subscription_suspended")
    assert client.get(f"/api/payments/{pay.id}", headers=h).status_code == 200


# --- cash of the day -------------------------------------------------------------------------------------------

def test_cash_of_the_day_by_method(
    client: TestClient, setup: Any, make_patient: Factory, make_practice: Factory, make_payment: Factory, auth_headers: Factory
) -> None:
    other = make_patient(setup.practice, first_name="Sami", last_name="Ben Ali")
    # Tunis day 30.10 = [29.10 23:00 UTC, 30.10 23:00 UTC)
    make_payment(setup.patient, 20_000, method="cash", paid_at=datetime(2026, 10, 29, 23, 0, tzinfo=UTC))
    make_payment(other, 15_500, method="cash", paid_at=datetime(2026, 10, 30, 22, 59, tzinfo=UTC))
    make_payment(other, 40_000, method="d17", paid_at=T0)
    make_payment(setup.patient, 99_000, method="cash", paid_at=datetime(2026, 10, 29, 22, 59, tzinfo=UTC))  # day before
    make_payment(setup.patient, 1_000, method="cash", paid_at=datetime(2026, 10, 30, 23, 0, tzinfo=UTC))  # day after
    make_payment(make_patient(make_practice()), 77_000, paid_at=T0)  # another practice
    body = client.get("/api/cash", headers=auth_headers(setup.owner)).json()
    assert body["day"] == "2026-10-30"
    assert body["totalMillimes"] == 75_500
    assert body["byMethod"] == {"cash": 35_500, "d17": 40_000, "flouci": 0, "card": 0, "cheque": 0, "transfer": 0, "other": 0}
    assert [p["amountMillimes"] for p in body["payments"]] == [15_500, 40_000, 20_000]
    yesterday = client.get("/api/cash?day=2026-10-29", headers=auth_headers(setup.owner)).json()
    assert yesterday["totalMillimes"] == 99_000


def test_cash_validates_the_day(client: TestClient, setup: Any, auth_headers: Factory) -> None:
    assert_problem(client.get("/api/cash?day=30/10/2026", headers=auth_headers(setup.owner)), 422, "validation")
    assert_problem(client.get("/api/cash"), 401, "unauthorized")


# --- balances --------------------------------------------------------------------------------------------------

def test_open_balances_largest_first(
    client: TestClient, setup: Any, make_patient: Factory, make_practice: Factory, make_treatment: Factory,
    make_payment: Factory, auth_headers: Factory,
) -> None:
    sami = make_patient(setup.practice, first_name="Sami", last_name="Ben Ali", phone="+21620000009")
    paid_up = make_patient(setup.practice)
    make_treatment(setup.patient, 100_000)
    make_payment(setup.patient, 40_000, paid_at=T0 - timedelta(days=3))
    make_payment(setup.patient, 10_000, paid_at=T0 - timedelta(days=1))
    make_treatment(sami, 250_000)
    make_treatment(paid_up, 30_000)
    make_payment(paid_up, 50_000)  # overpaid → not listed
    make_treatment(make_patient(make_practice()), 999_000)
    body = client.get("/api/balances", headers=auth_headers(setup.owner)).json()
    assert body == [
        {"patientId": sami.id, "name": "Sami Ben Ali", "phone": "+21620000009", "dueMillimes": 250_000, "lastPaymentAt": None},
        {"patientId": setup.patient.id, "name": "Amira Trabelsi", "phone": setup.patient.phone, "dueMillimes": 50_000,
         "lastPaymentAt": "2026-10-29T09:00:00+01:00"},
    ]
    assert len(client.get("/api/balances?limit=1", headers=auth_headers(setup.owner)).json()) == 1
    assert_problem(client.get("/api/balances?limit=0", headers=auth_headers(setup.owner)), 422, "validation")
    assert_problem(client.get("/api/balances?limit=501", headers=auth_headers(setup.owner)), 422, "validation")
