"""Admin customer master (backlog A1, sections 11.2, 12, 15): ``/api/admin/practices…`` and ``/api/admin/slug-available``."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from daftar.catalog import DEFAULT_CATALOGS
from daftar.tables import appointment, patient, practice, service
from tests.helpers import assert_problem, login
from tests.termine.conftest import Factory

HOURS = {"1": [["09:00", "13:00"], ["15:00", "19:00"]], "3": [["09:00", "13:00"]], "6": [["09:00", "12:00"]]}


def full_body(**override: Any) -> dict[str, Any]:
    body = {
        "name": "Cabinet Dr Ben Salah",
        "nameAr": "عيادة الدكتور بن صالح",
        "slug": "dr-ben-salah",
        "specialty": "kinesitherapeute",
        "contactName": "Leïla Ben Salah",
        "phone": "71 234 567",
        "whatsapp": "20 345 678",
        "email": "contact@bensalah.tn",
        "address": "5 avenue Habib Bourguiba",
        "postalCode": "4000",
        "city": "Sousse",
        "governorate": "sousse",
        "mapsUrl": "https://maps.app.goo.gl/xyz",
        "taxId": "1234567/B",
        "status": "pilot",
        "pilotUntil": "2026-12-31",
        "adminNotes": "Rencontrée au salon",
        "weeklyHours": HOURS,
        "practitioners": [{"name": "Leïla Ben Salah", "title": "Mme"}, {"name": "Sami Ben Salah"}],
        "onlineBooking": {"enabled": True, "autoConfirm": False, "horizonDays": 21, "minNoticeHours": 4,
                          "maxPerDay": 10, "blockNoShows": 2},
    }
    body.update(override)
    return body


@pytest.fixture
def admin(as_user: Factory) -> dict[str, str]:
    return as_user(role="admin")


def test_admin_creates_a_practice_with_full_data(client: TestClient, admin: dict[str, str], db: Any) -> None:
    res = client.post("/api/admin/practices", json=full_body(), headers=admin)
    assert res.status_code == 201, res.text
    body = res.json()
    p = body["practice"]
    assert (p["name"], p["nameAr"], p["slug"], p["specialty"]) == (
        "Cabinet Dr Ben Salah", "عيادة الدكتور بن صالح", "dr-ben-salah", "kinesitherapeute")
    assert (p["phone"], p["whatsapp"], p["email"], p["governorate"]) == ("+21671234567", "+21620345678", "contact@bensalah.tn", "sousse")
    assert (p["status"], p["paidUntil"], p["pilotUntil"], p["planCode"], p["adminNotes"]) == (
        "pilot", "2026-12-31", "2026-12-31", "pilot", "Rencontrée au salon")
    assert p["weeklyHours"]["1"] == [["09:00", "13:00"], ["15:00", "19:00"]] and p["weeklyHours"]["2"] == []
    assert p["onlineBooking"] == full_body()["onlineBooking"]
    assert [(d["name"], d["title"], d["sort"]) for d in p["practitioners"]] == [("Leïla Ben Salah", "Mme", 1), ("Sami Ben Salah", "Dr.", 2)]
    # no services given → the default catalog of the specialty
    assert [(s["nameFr"], s["durationMin"], s["onlineBookable"]) for s in p["services"]] == [
        (i.name_fr, i.duration_min, i.online_bookable) for i in DEFAULT_CATALOGS["kinesitherapeute"]]
    assert p["owner"] is None and p["bookingUrl"] == "https://dr-ben-salah.daftar.omarfourati.de"
    assert len(body["invitation"]["token"]) >= 40 and body["invitation"]["expiresAt"] == "2026-11-06T09:00:00+01:00"
    # the owner invitation works and makes the owner of this practice
    res = client.post("/api/invitations/accept", json={"token": body["invitation"]["token"], "name": "Leïla",
                                                       "email": "leila@bensalah.tn", "password": "mot-de-passe-solide"})
    assert res.status_code == 201, res.text
    assert res.json()["user"]["role"] == "owner" and res.json()["user"]["practice"]["slug"] == "dr-ben-salah"


def test_admin_can_give_an_own_catalog(client: TestClient, admin: dict[str, str]) -> None:
    services = [{"nameFr": "Séance individuelle", "nameAr": "حصة", "durationMin": 50, "priceMillimes": 60_000,
                 "onlineBookable": True}, {"nameFr": "Bilan", "durationMin": 90}]
    res = client.post("/api/admin/practices", json=full_body(specialty="psychologue", services=services), headers=admin)
    assert res.status_code == 201, res.text
    got = res.json()["practice"]["services"]
    assert [(s["nameFr"], s["durationMin"], s["priceMillimes"], s["onlineBookable"], s["sort"]) for s in got] == [
        ("Séance individuelle", 50, 60_000, True, 1), ("Bilan", 90, None, False, 2)]


def test_minimal_practice_gets_defaults(client: TestClient, admin: dict[str, str]) -> None:
    body = {"name": "Cabinet Minimal", "slug": "cabinet-minimal", "specialty": "dentiste", "contactName": "Dr X",
            "phone": "20123456", "address": "Rue 1", "city": "Tunis", "governorate": "tunis"}
    res = client.post("/api/admin/practices", json=body, headers=admin)
    assert res.status_code == 201, res.text
    p = res.json()["practice"]
    assert (p["status"], p["planCode"], p["pilotUntil"], p["practitioners"], p["brandColor"]) == ("pilot", "pilot", None, [], "#0f766e")
    assert p["weeklyHours"]["1"] == [["08:00", "12:30"], ["14:00", "18:00"]]
    assert p["onlineBooking"]["enabled"] is False
    assert [s["nameFr"] for s in p["services"] if s["onlineBookable"]] == ["Consultation", "Contrôle", "Détartrage"]


@pytest.mark.parametrize(
    "missing", ["name", "slug", "specialty", "contactName", "phone", "address", "city", "governorate"]
)
def test_required_fields(client: TestClient, admin: dict[str, str], missing: str) -> None:
    body = full_body()
    del body[missing]
    assert_problem(client.post("/api/admin/practices", json=body, headers=admin), 422, "validation")


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"slug": "ab"}, "slug_invalid"),
        ({"slug": "Cabinet Lac"}, "slug_invalid"),
        ({"slug": "-lac"}, "slug_invalid"),
        ({"slug": "admin"}, "slug_reserved"),
        ({"slug": "www"}, "slug_reserved"),
        ({"slug": "demo-ab12cd34"}, "slug_reserved"),  # demo practices only
        ({"specialty": "chirurgien"}, "validation"),
        ({"governorate": "paris"}, "validation"),
        ({"phone": "123"}, "invalid_phone"),
        ({"status": "frozen"}, "validation"),
        ({"planCode": "gold"}, "invalid_plan"),
        ({"weeklyHours": {"1": [["18:00", "08:00"]]}}, "invalid_hours"),
        ({"practitioners": [{"name": ""}]}, "validation"),
        ({"practitioners": [{"name": "X"}] * 51}, "validation"),
        ({"services": [{"nameFr": "X", "durationMin": 2}]}, "validation"),
        ({"onlineBooking": {"enabled": True, "horizonDays": 0}}, "validation"),
        ({"adminNotes": "x" * 5001}, "validation"),
        ({"mapsUrl": "javascript:alert(1)"}, "validation"),
        ({"address": ""}, "validation"),
    ],
)
def test_create_validation(client: TestClient, admin: dict[str, str], override: dict[str, Any], code: str, db: Any) -> None:
    assert_problem(client.post("/api/admin/practices", json=full_body(**override), headers=admin), 422, code)
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(practice)).scalar_one() == 0


def test_slug_is_lower_cased_and_must_be_free(client: TestClient, admin: dict[str, str], make_practice: Factory) -> None:
    make_practice(slug="cabinet-lac")
    assert_problem(client.post("/api/admin/practices", json=full_body(slug="Cabinet-Lac"), headers=admin), 409, "slug_taken")
    res = client.post("/api/admin/practices", json=full_body(slug="  Dr-Ben-Salah "), headers=admin)
    assert res.status_code == 201 and res.json()["practice"]["slug"] == "dr-ben-salah"


def test_slug_available(client: TestClient, admin: dict[str, str], make_practice: Factory) -> None:
    taken = make_practice(slug="cabinet-lac")

    def check(slug: str, **params: Any) -> dict[str, Any]:
        res = client.get("/api/admin/slug-available", params={"slug": slug, **params}, headers=admin)
        assert res.status_code == 200, res.text
        return res.json()

    assert check("cabinet-sfax") == {"available": True, "reason": None}
    assert check("cabinet-lac") == {"available": False, "reason": "taken"}
    assert check("Cabinet-Lac") == {"available": False, "reason": "taken"}
    assert check("cabinet-lac", practiceId=taken.id) == {"available": True, "reason": None}  # its own slug when editing
    assert check("ab") == {"available": False, "reason": "invalid"}
    assert check("api") == {"available": False, "reason": "reserved"}
    assert check("demo-12345678") == {"available": False, "reason": "reserved"}
    assert check("") == {"available": False, "reason": "invalid"}


def test_list_practices_with_usage(
    client: TestClient, admin: dict[str, str], make_practice: Factory, make_user: Factory, make_patient: Factory,
    make_appointment: Factory, clock: Any,
) -> None:
    old = make_practice("Ancien", slug="ancien", created_at=clock.now() - timedelta(days=40), city="Sfax", governorate="sfax")
    new = make_practice("Nouveau", slug="nouveau", specialty="dentiste")
    demo = make_practice("Démo", slug="demo-abcdefgh", is_demo=True, demo_expires_at=clock.now() + timedelta(hours=24))
    make_user(old, "owner")
    make_user(old, "assistant")
    pat = make_patient(old, created_at=clock.now() - timedelta(days=20))
    make_appointment(pat, starts_at=clock.now() + timedelta(days=1), created_at=clock.now() - timedelta(days=10))
    make_appointment(pat, starts_at=clock.now() + timedelta(days=2), created_at=clock.now() - timedelta(days=2))
    res = client.get("/api/admin/practices", headers=admin)
    assert res.status_code == 200, res.text
    items = res.json()
    assert [p["name"] for p in items] == ["Nouveau", "Ancien"]  # newest first, demos hidden
    first_old = items[1]
    assert first_old == {
        "id": old.id, "name": "Ancien", "slug": "ancien", "city": "Sfax", "governorate": "sfax",
        "specialty": "generaliste", "status": "pilot", "planCode": "pilot", "paidUntil": None, "isDemo": False,
        "createdAt": "2026-09-20T09:00:00+01:00", "users": 2, "patients": 1, "appointments": 2, "appointmentsWeek": 1,
        "lastActivityAt": "2026-10-28T09:00:00+01:00",
    }
    assert items[0]["lastActivityAt"] is None and items[0]["users"] == 0
    with_demos = client.get("/api/admin/practices?demo=true", headers=admin).json()
    assert [(p["id"], p["isDemo"]) for p in with_demos] == [(demo.id, True), (new.id, False), (old.id, False)]
    assert [p["name"] for p in client.get("/api/admin/practices?demo=false", headers=admin).json()] == ["Nouveau", "Ancien"]


def test_get_one_practice_with_everything(
    client: TestClient, admin: dict[str, str], make_practice: Factory, make_user: Factory
) -> None:
    created = client.post("/api/admin/practices", json=full_body(), headers=admin).json()["practice"]
    owner = make_user(type("P", (), {"id": created["id"]})(), "owner", name="Leïla", email="leila@bensalah.tn")
    res = client.get(f"/api/admin/practices/{created['id']}", headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["owner"] == {"id": owner.id, "name": "Leïla", "email": "leila@bensalah.tn"}
    assert body["adminNotes"] == "Rencontrée au salon" and len(body["displayToken"]) == 32
    assert (body["users"], body["patients"], body["appointments"]) == (1, 0, 0)
    assert_problem(client.get("/api/admin/practices/999999", headers=admin), 404, "not_found")


def test_admin_patches_everything(client: TestClient, admin: dict[str, str], make_practice: Factory, db: Any) -> None:
    make_practice(slug="pris")
    created = client.post("/api/admin/practices", json=full_body(), headers=admin).json()["practice"]
    url = f"/api/admin/practices/{created['id']}"
    res = client.patch(url, json={"slug": "ben-salah-sousse", "status": "active", "paidUntil": "2027-10-30",
                                  "planCode": "cabinet_annuel", "adminNotes": "Payé par virement", "name": "Cabinet BS",
                                  "onlineBooking": {"autoConfirm": True}}, headers=admin)
    assert res.status_code == 200, res.text
    p = res.json()
    assert (p["slug"], p["status"], p["paidUntil"], p["planCode"], p["adminNotes"], p["name"]) == (
        "ben-salah-sousse", "active", "2027-10-30", "cabinet_annuel", "Payé par virement", "Cabinet BS")
    assert p["onlineBooking"]["autoConfirm"] is True and p["onlineBooking"]["horizonDays"] == 21
    assert client.patch(url, json={"pilotUntil": "2027-01-15"}, headers=admin).json()["paidUntil"] == "2027-01-15"
    assert client.patch(url, json={"paidUntil": None}, headers=admin).json()["paidUntil"] is None
    assert_problem(client.patch(url, json={"slug": "pris"}, headers=admin), 409, "slug_taken")
    assert_problem(client.patch(url, json={"slug": "status"}, headers=admin), 422, "slug_reserved")
    assert_problem(client.patch(url, json={"status": "gelé"}, headers=admin), 422, "validation")
    assert_problem(client.patch(url, json={"planCode": "gold"}, headers=admin), 422, "invalid_plan")
    assert client.patch(url, json={"slug": "ben-salah-sousse"}, headers=admin).status_code == 200  # unchanged slug is fine
    assert_problem(client.patch("/api/admin/practices/999999", json={"name": "X"}, headers=admin), 404, "not_found")


def test_admin_deletes_a_practice_with_everything(
    client: TestClient, admin: dict[str, str], make_practice: Factory, make_user: Factory, make_patient: Factory,
    make_appointment: Factory, db: Any,
) -> None:
    p, keep = make_practice(), make_practice()
    owner = make_user(p, "owner")
    make_appointment(make_patient(p))
    make_patient(keep)
    assert client.delete(f"/api/admin/practices/{p.id}", headers=admin).status_code == 204
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(service).where(service.c.practice_id == p.id)).scalar_one() == 0
    assert login(client, owner.email).status_code == 401
    assert_problem(client.delete(f"/api/admin/practices/{p.id}", headers=admin), 404, "not_found")


def test_new_owner_invitation(client: TestClient, admin: dict[str, str], make_practice: Factory) -> None:
    p = make_practice("Cabinet Lac")
    res = client.post(f"/api/admin/practices/{p.id}/invitation", headers=admin)
    assert res.status_code == 201, res.text
    token = res.json()["token"]
    assert res.json()["expiresAt"] == "2026-11-06T09:00:00+01:00"
    assert client.post("/api/invitations/preview", json={"token": token}).json() == {"practiceName": "Cabinet Lac", "role": "owner"}
    assert_problem(client.post("/api/admin/practices/999999/invitation", headers=admin), 404, "not_found")


def test_owner_reset_link(client: TestClient, admin: dict[str, str], make_practice: Factory, make_user: Factory) -> None:
    p = make_practice("Cabinet Lac")
    assert_problem(client.post(f"/api/admin/practices/{p.id}/owner-reset-link", headers=admin), 404, "owner_missing")
    make_user(p, "assistant")
    owner = make_user(p, "owner", email="titulaire@lac.tn")
    res = client.post(f"/api/admin/practices/{p.id}/owner-reset-link", headers=admin)
    assert res.status_code == 201, res.text
    assert res.json()["expiresAt"] == "2026-10-31T09:00:00+01:00"
    preview = client.post("/api/password-reset/preview", json={"token": res.json()["token"]})
    assert preview.json() == {"email": "titulaire@lac.tn", "practiceName": "Cabinet Lac"}
    accepted = client.post("/api/password-reset/accept", json={"token": res.json()["token"], "password": "nouveau-mot-de-passe"})
    assert accepted.status_code == 200 and accepted.json()["user"]["id"] == owner.id
    assert_problem(client.post("/api/admin/practices/999999/owner-reset-link", headers=admin), 404, "not_found")


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_only_the_admin(client: TestClient, as_user: Factory, make_practice: Factory, role: str) -> None:
    p = make_practice()
    h = as_user(p, role)
    for method, url in (
        ("get", "/api/admin/practices"), ("post", "/api/admin/practices"), ("get", f"/api/admin/practices/{p.id}"),
        ("patch", f"/api/admin/practices/{p.id}"), ("delete", f"/api/admin/practices/{p.id}"),
        ("post", f"/api/admin/practices/{p.id}/invitation"), ("post", f"/api/admin/practices/{p.id}/owner-reset-link"),
        ("get", "/api/admin/slug-available?slug=abc"),
    ):
        kwargs: dict[str, Any] = {"headers": h}
        if method in ("post", "patch") and url.endswith(("practices", f"{p.id}")):
            kwargs["json"] = full_body()
        assert_problem(getattr(client, method)(url, **kwargs), 403, "forbidden")
        no_token = {k: v for k, v in kwargs.items() if k != "headers"}
        assert_problem(getattr(client, method)(url, **no_token), 401, "unauthorized")
