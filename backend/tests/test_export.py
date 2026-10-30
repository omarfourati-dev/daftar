"""Export of all data of a practice (section 5, E4): owner only, JSON download, never secrets or hashes."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert, select

from daftar.tables import app_user, feedback, import_template, invoice, practice
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def filled(
    db: Engine, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_treatment: Factory, make_payment: Factory, make_queue_entry: Factory, make_service: Factory,
    make_invitation: Factory,
) -> Any:
    lac = make_practice("Cabinet Lac", slug="cabinet-lac", admin_notes="Notes internes d'Omar", practitioners=["Dr. Salah"])
    owner = make_user(lac, "owner", name="Dr. Owner")
    make_user(lac, "assistant", name="Sonia")
    make_service(lac, "Consultation", 20, price_millimes=40_000)
    pat = make_patient(lac, first_name="Amira", last_name="Trabelsi", alerts="Allergie")
    appt = make_appointment(pat, booking_token_hash="a" * 64, practitioner_id=lac.practitioners[0].id)
    make_treatment(pat, 120_000)
    make_payment(pat, 50_000, appointment_id=appt.id, is_deposit=True)
    make_queue_entry(lac, 1, patient_id=pat.id, appointment_id=appt.id, name="Amira", ticket_token="b" * 32)
    make_invitation(lac, "dentist")
    with db.begin() as conn:
        conn.execute(insert(feedback).values(practice_id=lac.id, user_id=owner.id, message="Super", created_at=T0))
        conn.execute(insert(import_template).values(practice_id=lac.id, name="Mon Excel", kind="patients",
                                                    mapping={"lastName": 0}, created_at=T0))
        conn.execute(insert(invoice).values(practice_id=lac.id, number="DAF-2026-0001", plan_code="cabinet_mensuel",
                                            period_start=T0.date(), period_end=T0.date().replace(month=11),
                                            amount_millimes=49_000, due_on=T0.date(), created_at=T0))
        hashes = [r[0] for r in conn.execute(select(app_user.c.password_hash))]
        display_token = conn.execute(select(practice.c.display_token).where(practice.c.id == lac.id)).scalar_one()
    other = make_practice("Cabinet Autre")
    make_patient(other, first_name="Etranger", last_name="Inconnu")
    return type("F", (), {"practice": lac, "owner": owner, "hashes": hashes, "display_token": display_token})


def test_owner_downloads_everything_of_the_practice(client: TestClient, filled: Any, auth_headers: Factory) -> None:
    res = client.get("/api/practice/export", headers=auth_headers(filled.owner))
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/json")
    assert res.headers["content-disposition"] == 'attachment; filename="daftar-export-cabinet-lac-2026-10-30.json"'
    assert res.headers["cache-control"] == "no-store"
    data = res.json()
    assert data["format"] == "daftar-export/1" and data["exportedAt"] == "2026-10-30T09:00:00+01:00"
    assert data["practice"]["name"] == "Cabinet Lac" and data["practice"]["slug"] == "cabinet-lac"
    assert {u["name"] for u in data["users"]} == {"Dr. Owner", "Sonia"}
    assert [p["firstName"] for p in data["patients"]] == ["Amira"]
    assert data["patients"][0]["alerts"] == "Allergie"
    assert len(data["appointments"]) == 1 and data["appointments"][0]["startsAt"] == "2026-10-30T10:00:00+01:00"
    assert [t["priceMillimes"] for t in data["treatments"]] == [120_000]
    assert [p["amountMillimes"] for p in data["payments"]] == [50_000]
    assert [s["nameFr"] for s in data["services"]] == ["Consultation"]
    assert [p["name"] for p in data["practitioners"]] == ["Dr. Salah"]
    assert len(data["queueEntries"]) == 1 and len(data["invitations"]) == 1
    assert [f["message"] for f in data["feedback"]] == ["Super"]
    assert [t["name"] for t in data["importTemplates"]] == ["Mon Excel"]
    assert [i["number"] for i in data["invoices"]] == ["DAF-2026-0001"]
    assert data["closures"] == []


def test_export_contains_no_secrets_and_nothing_of_other_practices(client: TestClient, filled: Any, auth_headers: Factory) -> None:
    text = client.get("/api/practice/export", headers=auth_headers(filled.owner)).text
    for secret in (*filled.hashes, filled.display_token, "a" * 64, "b" * 32):
        assert secret not in text
    for field in ("passwordHash", "tokenHash", "bookingTokenHash", "ticketToken", "displayToken", "tokenVersion",
                  "adminNotes", "fileBytes"):
        assert field not in text, field
    assert "Notes internes" not in text
    assert "Etranger" not in text and "Cabinet Autre" not in text


def test_export_works_with_a_suspended_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory
) -> None:
    owner = make_user(make_practice(status="suspended"), "owner")
    assert client.get("/api/practice/export", headers=auth_headers(owner)).status_code == 200


@pytest.mark.parametrize("role", ["dentist", "assistant", "admin"])
def test_export_is_for_the_owner(client: TestClient, make_user: Factory, auth_headers: Factory, role: str) -> None:
    assert_problem(client.get("/api/practice/export", headers=auth_headers(make_user(role=role))), 403, "forbidden")
    assert_problem(client.get("/api/practice/export"), 401, "unauthorized")
