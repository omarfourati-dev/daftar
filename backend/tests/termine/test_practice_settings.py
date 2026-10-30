"""``/api/practice`` (owner settings without admin fields) and the waiting-room screen token."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.tables import practice
from tests.helpers import assert_problem
from tests.termine.conftest import Factory

HOURS = {
    "1": [["08:30", "12:00"], ["15:00", "19:00"]],
    "2": [["08:30", "12:00"]],
    "3": [],
    "4": [["08:30", "12:00"], ["15:00", "19:00"]],
    "5": [["08:30", "12:00"]],
    "6": [["09:00", "13:00"]],
    "7": [],
}


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice(
        "Cabinet du Lac",
        slug="cabinet-lac",
        specialty="dentiste",
        name_ar="عيادة البحيرة",
        contact_name="Dr Amira Ben Ali",
        phone="+21671123456",
        city="Tunis",
        governorate="tunis",
        admin_notes="paie en espèces",
    )


def test_get_practice_returns_the_settings_without_admin_notes(client: TestClient, lac: Any, as_user: Factory) -> None:
    for role in ("owner", "dentist", "assistant"):
        res = client.get("/api/practice", headers=as_user(lac, role))
        assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == lac.id
    assert body["name"] == "Cabinet du Lac" and body["nameAr"] == "عيادة البحيرة"
    assert (body["slug"], body["specialty"], body["status"]) == ("cabinet-lac", "dentiste", "pilot")
    assert body["contactName"] == "Dr Amira Ben Ali" and body["phone"] == "+21671123456"
    assert (body["city"], body["governorate"], body["whatsapp"], body["email"]) == ("Tunis", "tunis", None, None)
    assert body["weeklyHours"]["1"] == [["08:00", "12:30"], ["14:00", "18:00"]] and body["weeklyHours"]["7"] == []
    assert (body["dayStart"], body["dayEnd"]) == ("08:00", "18:00")
    assert (body["slotMinutes"], body["defaultDurationMin"], body["brandColor"]) == (15, 30, "#0f766e")
    assert len(body["displayToken"]) == 32 and body["isDemo"] is False and body["demoExpiresAt"] is None
    assert body["onlineBooking"] == {
        "enabled": False, "autoConfirm": False, "horizonDays": 30, "minNoticeHours": 2, "maxPerDay": 20, "blockNoShows": 2,
    }
    assert "{patient}" in body["reminderTemplateFr"] and "{time}" in body["reminderTemplateAr"]
    assert body["createdAt"] == "2026-10-30T09:00:00+01:00"
    assert "adminNotes" not in body and "paie en espèces" not in res.text


def test_get_practice_needs_a_token_and_a_practice(client: TestClient, as_user: Factory) -> None:
    assert_problem(client.get("/api/practice"), 401, "unauthorized")
    assert_problem(client.get("/api/practice", headers=as_user(role="admin")), 403, "forbidden")


def test_each_user_sees_only_their_own_practice(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    mine, other = make_practice("Mine"), make_practice("Other")
    assert client.get("/api/practice", headers=as_user(mine, "assistant")).json()["name"] == "Mine"
    assert client.get("/api/practice", headers=as_user(other, "assistant")).json()["name"] == "Other"


def test_owner_patches_the_settings(client: TestClient, lac: Any, as_user: Factory, db: Any) -> None:
    body = {
        "name": "Cabinet Dentaire du Lac",
        "nameAr": "عيادة الأسنان",
        "contactName": "Dr Karim",
        "phone": "71 999 888",
        "whatsapp": "+216 20 123 456",
        "email": "Contact@Cabinet-Lac.TN",
        "address": "12 rue du Lac Léman",
        "postalCode": "1053",
        "city": "Les Berges du Lac",
        "governorate": "tunis",
        "mapsUrl": "https://maps.app.goo.gl/abc",
        "descriptionFr": "Soins dentaires pour toute la famille.",
        "descriptionAr": "علاج الأسنان لكل العائلة.",
        "taxId": "1234567/A/M/000",
        "brandColor": "#1D4ED8",
        "weeklyHours": HOURS,
        "slotMinutes": 20,
        "defaultDurationMin": 40,
        "reminderTemplateFr": "Bonjour {patient}, RDV le {date} à {time}.",
        "reminderTemplateAr": "مرحبا {patient}",
        "specialty": "orl",
        "onlineBooking": {"enabled": True, "autoConfirm": True, "horizonDays": 60, "minNoticeHours": 12,
                          "maxPerDay": 8, "blockNoShows": 3},
    }
    res = client.patch("/api/practice", json=body, headers=as_user(lac, "owner"))
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["phone"] == "+21671999888" and out["whatsapp"] == "+21620123456"
    assert out["email"] == "contact@cabinet-lac.tn" and out["brandColor"] == "#1d4ed8"
    assert out["weeklyHours"] == HOURS and (out["dayStart"], out["dayEnd"]) == ("08:30", "19:00")
    assert (out["slotMinutes"], out["defaultDurationMin"], out["specialty"]) == (20, 40, "orl")
    assert out["onlineBooking"] == body["onlineBooking"]
    for key in ("name", "nameAr", "contactName", "address", "postalCode", "city", "mapsUrl", "descriptionFr",
                "descriptionAr", "taxId", "reminderTemplateFr", "reminderTemplateAr"):
        assert out[key] == body[key], key
    assert client.get("/api/practice", headers=as_user(lac, "assistant")).json() == out


def test_patch_is_partial_and_clears_optional_fields_with_null(client: TestClient, lac: Any, as_user: Factory) -> None:
    owner = as_user(lac, "owner")
    client.patch("/api/practice", json={"whatsapp": "20123456", "email": "a@b.tn"}, headers=owner)
    res = client.patch("/api/practice", json={"onlineBooking": {"enabled": True}}, headers=owner)
    out = res.json()
    assert out["whatsapp"] == "+21620123456" and out["name"] == "Cabinet du Lac"
    assert out["onlineBooking"]["enabled"] is True and out["onlineBooking"]["horizonDays"] == 30
    out = client.patch("/api/practice", json={"whatsapp": None, "email": "", "governorate": None}, headers=owner).json()
    assert (out["whatsapp"], out["email"], out["governorate"]) == (None, None, None)


def test_owner_cannot_change_admin_fields(client: TestClient, lac: Any, as_user: Factory, db: Any) -> None:
    res = client.patch(
        "/api/practice",
        json={"slug": "autre-slug", "status": "active", "adminNotes": "x", "paidUntil": "2030-01-01",
              "pilotUntil": "2030-01-01", "planCode": "cabinet_annuel", "isDemo": True, "displayToken": "0" * 32},
        headers=as_user(lac, "owner"),
    )
    assert res.status_code == 200, res.text
    with db.connect() as conn:
        row = conn.execute(select(practice).where(practice.c.id == lac.id)).one()
    assert (row.slug, row.status, row.admin_notes, row.paid_until, row.plan_code, row.is_demo) == (
        "cabinet-lac", "pilot", "paie en espèces", None, "pilot", False)
    assert row.display_token == lac.display_token


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": ""}, "validation"),
        ({"name": None}, "validation"),
        ({"phone": None}, "validation"),
        ({"weeklyHours": None}, "validation"),
        ({"name": "x" * 121}, "validation"),
        ({"phone": "123"}, "invalid_phone"),
        ({"whatsapp": "abc"}, "invalid_phone"),
        ({"email": "pas-un-email"}, "validation"),
        ({"governorate": "paris"}, "validation"),
        ({"brandColor": "teal"}, "validation"),
        ({"weeklyHours": {"1": [["12:00", "08:00"]]}}, "invalid_hours"),
        ({"slotMinutes": 7}, "validation"),
        ({"defaultDurationMin": 4}, "validation"),
        ({"defaultDurationMin": 481}, "validation"),
        ({"mapsUrl": "javascript:alert(1)"}, "validation"),
        ({"mapsUrl": "http://maps.example.tn"}, "validation"),
        ({"specialty": "chirurgien"}, "validation"),
        ({"postalCode": "12345678901"}, "validation"),
        ({"descriptionFr": "x" * 2001}, "validation"),
        ({"reminderTemplateFr": "x" * 1001}, "validation"),
        ({"onlineBooking": {"horizonDays": 0}}, "validation"),
        ({"onlineBooking": {"horizonDays": 366}}, "validation"),
        ({"onlineBooking": {"minNoticeHours": 169}}, "validation"),
        ({"onlineBooking": {"maxPerDay": 0}}, "validation"),
        ({"onlineBooking": {"blockNoShows": 21}}, "validation"),
        ({"onlineBooking": {"enabled": "peut-être"}}, "validation"),
    ],
)
def test_patch_validation(client: TestClient, lac: Any, as_user: Factory, body: dict[str, Any], code: str) -> None:
    assert_problem(client.patch("/api/practice", json=body, headers=as_user(lac, "owner")), 422, code)


@pytest.mark.parametrize("role", ["dentist", "assistant"])
def test_only_the_owner_changes_settings(client: TestClient, lac: Any, as_user: Factory, role: str) -> None:
    headers = as_user(lac, role)
    assert_problem(client.patch("/api/practice", json={"name": "X"}, headers=headers), 403, "forbidden")
    assert_problem(client.post("/api/practice/display-token", headers=headers), 403, "forbidden")


def test_patch_needs_a_token(client: TestClient) -> None:
    assert_problem(client.patch("/api/practice", json={"name": "X"}), 401, "unauthorized")
    assert_problem(client.post("/api/practice/display-token"), 401, "unauthorized")


def test_a_suspended_practice_cannot_change_settings(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    owner = as_user(make_practice(status="suspended"), "owner")
    assert_problem(client.patch("/api/practice", json={"name": "X"}, headers=owner), 402, "subscription_suspended")
    assert_problem(client.post("/api/practice/display-token", headers=owner), 402, "subscription_suspended")
    assert client.get("/api/practice", headers=owner).status_code == 200


def test_new_display_token(client: TestClient, lac: Any, as_user: Factory) -> None:
    owner = as_user(lac, "owner")
    res = client.post("/api/practice/display-token", headers=owner)
    assert res.status_code == 200, res.text
    token = res.json()["displayToken"]
    assert len(token) == 32 and all(c in "0123456789abcdef" for c in token) and token != lac.display_token
    assert client.get("/api/practice", headers=owner).json()["displayToken"] == token
    assert client.post("/api/practice/display-token", headers=owner).json()["displayToken"] != token


def test_day_range_is_null_when_the_practice_is_never_open(client: TestClient, lac: Any, as_user: Factory) -> None:
    out = client.patch("/api/practice", json={"weeklyHours": {}}, headers=as_user(lac, "owner")).json()
    assert out["weeklyHours"] == {str(d): [] for d in range(1, 8)}
    assert (out["dayStart"], out["dayEnd"]) == (None, None)
