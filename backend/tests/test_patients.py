"""Patients (sections 5, 15): list/search, file with alerts, same phone, reliability, appointments, ledger, delete."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from daftar.tables import appointment, patient, payment, queue_entry, treatment
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def owner(make_practice: Factory, make_user: Factory) -> Any:
    return make_user(make_practice(), "owner")


def _practice_of(user: Any) -> Any:
    return type("P", (), {"id": user.practice_id})()


# --- list and search -------------------------------------------------------------------------------------------

def test_list_needs_a_staff_token(client: TestClient, make_user: Factory, auth_headers: Factory) -> None:
    assert_problem(client.get("/api/patients"), 401, "unauthorized")
    assert_problem(client.get("/api/patients", headers=auth_headers(make_user(role="admin"))), 403, "forbidden")


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_list_shows_only_the_own_practice_sorted_by_name(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, auth_headers: Factory, role: str
) -> None:
    mine, other = make_practice(), make_practice()
    make_patient(mine, last_name="Trabelsi", first_name="Amira")
    make_patient(mine, last_name="Ben Ali", first_name="Sami")
    make_patient(other, last_name="Abidi", first_name="Foreign")
    res = client.get("/api/patients", headers=auth_headers(make_user(mine, role)))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    assert [p["lastName"] for p in body["items"]] == ["Ben Ali", "Trabelsi"]


def test_list_pages_with_limit_and_offset(
    client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory
) -> None:
    for name in ("A", "B", "C", "D"):
        make_patient(_practice_of(owner), last_name=name)
    res = client.get("/api/patients?limit=2&offset=1", headers=auth_headers(owner)).json()
    assert res["total"] == 4
    assert [p["lastName"] for p in res["items"]] == ["B", "C"]


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1", "limit=abc"])
def test_list_rejects_bad_paging(client: TestClient, owner: Any, auth_headers: Factory, query: str) -> None:
    assert_problem(client.get(f"/api/patients?{query}", headers=auth_headers(owner)), 422, "validation")


def test_search_by_name_parts_ignores_case(
    client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory
) -> None:
    p = _practice_of(owner)
    make_patient(p, first_name="Amira", last_name="Trabelsi")
    make_patient(p, first_name="Amine", last_name="Jlassi")
    make_patient(p, first_name="Sami", last_name="Ben Amor")

    def names(q: str) -> list[str]:
        return [x["firstName"] for x in client.get("/api/patients", params={"q": q}, headers=auth_headers(owner)).json()["items"]]

    assert names("ami") == ["Sami", "Amine", "Amira"]  # sorted by last name: Ben Amor, Jlassi, Trabelsi
    assert names("AMIRA") == ["Amira"]
    assert names("trabelsi amira") == ["Amira"]  # every word must match first or last name
    assert names("amor sami") == ["Sami"]
    assert names("") == ["Sami", "Amine", "Amira"]


def test_search_escapes_like_wildcards(client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory) -> None:
    make_patient(_practice_of(owner), first_name="Amira", last_name="Trabelsi")
    for q in ("%", "_", "\\"):
        res = client.get("/api/patients", params={"q": q}, headers=auth_headers(owner)).json()
        assert res["total"] == 0, q


def test_search_by_phone_digits(client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory) -> None:
    p = _practice_of(owner)
    make_patient(p, first_name="Amira", phone="+21620123456")
    make_patient(p, first_name="Sami", phone="+21698765432")

    def names(q: str) -> list[str]:
        return [x["firstName"] for x in client.get("/api/patients", params={"q": q}, headers=auth_headers(owner)).json()["items"]]

    assert names("20 123") == ["Amira"]
    assert names("20.12.34.56") == ["Amira"]
    assert names("+216 98 765 432") == ["Sami"]
    assert names("0021698765432") == ["Sami"]
    assert names("555") == []


def test_summary_counts_reliability_balance_and_next_appointment(
    client: TestClient,
    owner: Any,
    make_patient: Factory,
    make_appointment: Factory,
    make_treatment: Factory,
    make_payment: Factory,
    auth_headers: Factory,
) -> None:
    pat = make_patient(_practice_of(owner), alerts="Allergie pénicilline")
    days = [-10, -9, -8, -7, -6]
    for d, status in zip(days, ["done", "done", "no_show", "cancelled", "no_show"], strict=True):
        make_appointment(pat, starts_at=T0 + timedelta(days=d), status=status)
    make_appointment(pat, starts_at=T0 + timedelta(days=5), status="scheduled")
    make_appointment(pat, starts_at=T0 + timedelta(days=2), status="cancelled")  # not the next one
    make_appointment(pat, starts_at=T0 + timedelta(days=3), status="confirmed")
    make_treatment(pat, 120_000)
    make_treatment(pat, 30_500)
    make_payment(pat, 50_000)
    item = client.get("/api/patients", headers=auth_headers(owner)).json()["items"][0]
    assert item == {
        "id": pat.id,
        "firstName": pat.first_name,
        "lastName": pat.last_name,
        "phone": pat.phone,
        "birthYear": None,
        "birthDate": None,
        "lang": "fr",
        "reminderConsent": False,
        "noShows": 2,
        "attended": 2,
        "dueMillimes": 100_500,
        "nextAppointmentAt": "2026-11-02T09:00:00+01:00",
        "hasAlerts": True,
    }


# --- create ----------------------------------------------------------------------------------------------------

NEW = {"firstName": " Amira ", "lastName": "Trabelsi", "phone": "20 123 456", "lang": "ar", "reminderConsent": True}


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_create_normalizes_and_returns_the_file(client: TestClient, make_user: Factory, auth_headers: Factory, role: str) -> None:
    user = make_user(role=role)
    res = client.post("/api/patients", json={**NEW, "birthYear": 1985, "notes": "Préfère le matin", "alerts": "Anticoagulant"},
                      headers=auth_headers(user))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["firstName"] == "Amira" and body["phone"] == "+21620123456"
    assert (body["lang"], body["reminderConsent"], body["birthYear"]) == ("ar", True, 1985)
    assert body["alerts"] == "Anticoagulant" and body["hasAlerts"] is True
    assert body["createdAt"] == "2026-10-30T09:00:00+01:00"
    assert (body["noShows"], body["attended"], body["cancelled"], body["dueMillimes"]) == (0, 0, 0, 0)
    assert body["samePhone"] == [] and body["nextAppointmentAt"] is None


def test_arabic_digits_from_an_arabic_keyboard(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    """Security review N1: "٢٠ ١٢٣ ٤٥٦" used to reach the database as "+216٢٠١٢٣٤٥٦" – a 500 with the name in the log."""
    res = client.post("/api/patients", json={**NEW, "phone": "٢٠ ١٢٣ ٤٥٦"}, headers=auth_headers(owner))
    assert res.status_code == 201, res.text
    assert res.json()["phone"] == "+21620123456"


def test_create_defaults(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    body = client.post("/api/patients", json={"firstName": "A", "lastName": "B", "phone": "+33612345678"},
                       headers=auth_headers(owner)).json()
    assert (body["lang"], body["reminderConsent"], body["notes"], body["alerts"]) == ("fr", False, "", "")


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"phone": "12"}, "invalid_phone"),
        ({"phone": ""}, "invalid_phone"),
        ({"phone": "２０１２３４５６"}, "invalid_phone"),  # full-width digits: 422, not a 500 at the CHECK (N1)
        ({"phone": "२०१२३४५६"}, "invalid_phone"),
        ({"firstName": ""}, "validation"),
        ({"lastName": "x" * 121}, "validation"),
        ({"birthYear": 1899}, "validation"),
        ({"birthYear": 2027}, "invalid_birth_year"),
        ({"lang": "de"}, "validation"),
        ({"alerts": "x" * 501}, "validation"),
        ({"notes": "x" * 5001}, "validation"),
    ],
)
def test_create_validates(client: TestClient, owner: Any, auth_headers: Factory, change: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/patients", json={**NEW, **change}, headers=auth_headers(owner)), 422, code)


def test_create_is_blocked_by_a_suspended_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory
) -> None:
    user = make_user(make_practice(status="suspended"), "assistant")
    assert_problem(client.post("/api/patients", json=NEW, headers=auth_headers(user)), 402, "subscription_suspended")
    assert client.get("/api/patients", headers=auth_headers(user)).status_code == 200


# --- file ------------------------------------------------------------------------------------------------------

def test_file_shows_same_phone_family_members_of_the_own_practice(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, auth_headers: Factory
) -> None:
    mine, other = make_practice(), make_practice()
    mother = make_patient(mine, first_name="Leila", last_name="Gharbi", phone="+21620000001")
    child = make_patient(mine, first_name="Yassine", last_name="Gharbi", phone="+21620000001")
    make_patient(mine, phone="+21620000002")
    make_patient(other, phone="+21620000001")
    body = client.get(f"/api/patients/{mother.id}", headers=auth_headers(make_user(mine, "dentist"))).json()
    assert body["samePhone"] == [{"id": child.id, "firstName": "Yassine", "lastName": "Gharbi"}]


def test_file_has_totals_and_cancelled(
    client: TestClient, owner: Any, make_patient: Factory, make_appointment: Factory, make_treatment: Factory,
    make_payment: Factory, auth_headers: Factory,
) -> None:
    pat = make_patient(_practice_of(owner), notes="Note")
    make_appointment(pat, starts_at=T0 - timedelta(days=3), status="cancelled")
    make_treatment(pat, 80_000)
    make_payment(pat, 100_000)
    body = client.get(f"/api/patients/{pat.id}", headers=auth_headers(owner)).json()
    assert (body["cancelled"], body["totalMillimes"], body["paidMillimes"], body["dueMillimes"]) == (1, 80_000, 100_000, -20_000)
    assert body["notes"] == "Note" and body["alerts"] == "" and body["hasAlerts"] is False


def test_file_of_another_practice_is_404(
    client: TestClient, owner: Any, make_practice: Factory, make_patient: Factory, auth_headers: Factory
) -> None:
    stranger = make_patient(make_practice())
    for path in (f"/api/patients/{stranger.id}", f"/api/patients/{stranger.id}/appointments",
                 f"/api/patients/{stranger.id}/ledger", "/api/patients/999999"):
        assert_problem(client.get(path, headers=auth_headers(owner)), 404, "not_found")
    assert_problem(client.patch(f"/api/patients/{stranger.id}", json={"notes": "x"}, headers=auth_headers(owner)), 404, "not_found")
    assert_problem(client.delete(f"/api/patients/{stranger.id}", headers=auth_headers(owner)), 404, "not_found")


# --- update ----------------------------------------------------------------------------------------------------

def test_patch_changes_only_the_sent_fields(client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory) -> None:
    pat = make_patient(_practice_of(owner), first_name="Amira", birth_year=1990, notes="old")
    res = client.patch(f"/api/patients/{pat.id}", json={"phone": "0021622333444", "notes": "new", "birthYear": None},
                       headers=auth_headers(owner))
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["firstName"], body["phone"], body["notes"], body["birthYear"]) == ("Amira", "+21622333444", "new", None)


@pytest.mark.parametrize(("change", "code"), [({"phone": "abc"}, "invalid_phone"), ({"firstName": ""}, "validation"),
                                              ({"lastName": None}, "validation"), ({"alerts": "x" * 501}, "validation")])
def test_patch_validates(client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory,
                         change: dict[str, Any], code: str) -> None:
    pat = make_patient(_practice_of(owner))
    assert_problem(client.patch(f"/api/patients/{pat.id}", json=change, headers=auth_headers(owner)), 422, code)


def test_patch_is_blocked_by_a_suspended_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, auth_headers: Factory
) -> None:
    practice_row = make_practice(status="suspended")
    pat = make_patient(practice_row)
    res = client.patch(f"/api/patients/{pat.id}", json={"notes": "x"}, headers=auth_headers(make_user(practice_row, "owner")))
    assert_problem(res, 402, "subscription_suspended")


# --- delete ----------------------------------------------------------------------------------------------------

def test_delete_is_for_the_owner_and_removes_everything_of_the_patient(
    client: TestClient,
    db: Engine,
    make_practice: Factory,
    make_user: Factory,
    make_patient: Factory,
    make_appointment: Factory,
    make_treatment: Factory,
    make_payment: Factory,
    make_queue_entry: Factory,
    auth_headers: Factory,
) -> None:
    practice_row = make_practice()
    pat, keep = make_patient(practice_row), make_patient(practice_row)
    appt = make_appointment(pat)
    make_appointment(keep, starts_at=T0 + timedelta(hours=3))
    make_treatment(pat, 1000, appointment_id=appt.id)
    make_payment(pat, 1000, appointment_id=appt.id)
    make_queue_entry(practice_row, 1, patient_id=pat.id, appointment_id=appt.id, name="X")
    for role in ("dentist", "assistant"):
        assert_problem(client.delete(f"/api/patients/{pat.id}", headers=auth_headers(make_user(practice_row, role))), 403, "forbidden")
    res = client.delete(f"/api/patients/{pat.id}", headers=auth_headers(make_user(practice_row, "owner")))
    assert res.status_code == 204, res.text
    with db.connect() as conn:
        for table in (appointment, treatment, payment, queue_entry):
            assert conn.execute(select(func.count()).select_from(table).where(table.c.patient_id == pat.id)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 1


def test_delete_is_blocked_by_a_suspended_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, auth_headers: Factory
) -> None:
    practice_row = make_practice(status="suspended")
    pat = make_patient(practice_row)
    res = client.delete(f"/api/patients/{pat.id}", headers=auth_headers(make_user(practice_row, "owner")))
    assert_problem(res, 402, "subscription_suspended")


# --- appointments and ledger -----------------------------------------------------------------------------------

def test_appointments_of_a_patient_newest_first(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_payment: Factory, make_service: Factory, auth_headers: Factory,
) -> None:
    practice_row = make_practice(practitioners=["Dr. Salah"])
    doctor = practice_row.practitioners[0]
    svc = make_service(practice_row, "Détartrage", 45)
    pat = make_patient(practice_row, first_name="Amira", last_name="Trabelsi", alerts="Diabète")
    other = make_patient(practice_row)
    old = make_appointment(pat, starts_at=T0 - timedelta(days=7), status="no_show")
    new = make_appointment(pat, starts_at=T0 + timedelta(days=1), duration_min=45, practitioner_id=doctor.id,
                           service_id=svc.id, reason="Douleur", deposit_required_millimes=20_000, status="confirmed")
    make_appointment(other)
    make_payment(pat, 15_000, appointment_id=new.id, is_deposit=True)
    make_payment(pat, 5_000, appointment_id=new.id, is_deposit=False)
    res = client.get(f"/api/patients/{pat.id}/appointments", headers=auth_headers(make_user(practice_row, "assistant")))
    assert res.status_code == 200, res.text
    items = res.json()
    assert [a["id"] for a in items] == [new.id, old.id]
    first = items[0]
    assert first["patient"] == {"id": pat.id, "firstName": "Amira", "lastName": "Trabelsi", "phone": pat.phone,
                                "noShows": 1, "alerts": "Diabète", "lang": "fr"}
    assert (first["practitionerId"], first["practitionerName"]) == (doctor.id, "Dr. Salah")
    assert (first["serviceId"], first["serviceName"]) == (svc.id, "Détartrage")
    assert first["startsAt"] == "2026-10-31T09:00:00+01:00" and first["endsAt"] == "2026-10-31T09:45:00+01:00"
    assert (first["durationMin"], first["reason"], first["status"], first["source"]) == (45, "Douleur", "confirmed", "staff")
    assert (first["depositRequiredMillimes"], first["depositPaidMillimes"]) == (20_000, 15_000)
    assert first["reminderSentAt"] is None and first["seriesId"] is None
    assert first["createdAt"] == "2026-10-30T09:00:00+01:00"
    assert {"notes", "patientNote"} <= set(first)


def test_ledger_lists_treatments_and_payments_with_totals(
    client: TestClient, make_practice: Factory, make_user: Factory, make_patient: Factory, make_treatment: Factory,
    make_payment: Factory, auth_headers: Factory,
) -> None:
    practice_row = make_practice()
    cashier = make_user(practice_row, "assistant", name="Sonia")
    pat = make_patient(practice_row, first_name="Amira", last_name="Trabelsi")
    t1 = make_treatment(pat, 150_000, label="Couronne", tooth="26")
    make_payment(pat, 50_000, method="cash", received_by=cashier.id, paid_at=T0 - timedelta(days=2))
    p2 = make_payment(pat, 25_000, method="d17", note="2e versement", paid_at=T0 - timedelta(days=1))
    make_treatment(make_patient(practice_row), 999)  # someone else's
    body = client.get(f"/api/patients/{pat.id}/ledger", headers=auth_headers(cashier)).json()
    assert (body["totalMillimes"], body["paidMillimes"], body["dueMillimes"]) == (150_000, 75_000, 75_000)
    assert body["treatments"] == [{
        "id": t1.id, "label": "Couronne", "tooth": "26", "priceMillimes": 150_000, "performedOn": None,
        "appointmentId": None, "createdAt": "2026-10-30T09:00:00+01:00",
    }]
    assert [p["id"] for p in body["payments"]] == [p2.id, p2.id - 1]  # newest first
    assert body["payments"][0] == {
        "id": p2.id, "patientId": pat.id, "patientName": "Amira Trabelsi", "amountMillimes": 25_000, "method": "d17",
        "paidAt": "2026-10-29T09:00:00+01:00", "appointmentId": None, "isDeposit": False, "note": "2e versement",
        "receivedByName": None,
    }
    assert body["payments"][1]["receivedByName"] == "Sonia"
