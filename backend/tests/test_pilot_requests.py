"""Pilot requests (section 5): public form with honeypot and rate limit, admin list/delete, deletion after 12 months."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, insert, select

from daftar.pilot import delete_old_pilot_requests
from daftar.tables import pilot_request
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]
URL = "/api/public/pilot-requests"
VALID = {"name": " Dr. Amira Trabelsi ", "practice": "Cabinet du Lac", "city": "Tunis", "phone": "20 123 456",
         "email": "Amira@Example.TN", "message": "Bonjour", "lang": "ar", "website": ""}


def _rows(db: Engine) -> list[Any]:
    with db.connect() as conn:
        return conn.execute(select(pilot_request).order_by(pilot_request.c.id)).all()


def test_a_request_is_stored_and_counted(client: TestClient, db: Engine) -> None:
    res = client.post(URL, json=VALID)
    assert res.status_code == 202, res.text
    (row,) = _rows(db)
    assert (row.name, row.practice, row.city, row.phone, row.email, row.message, row.lang) == (
        "Dr. Amira Trabelsi", "Cabinet du Lac", "Tunis", "+21620123456", "amira@example.tn", "Bonjour", "ar"
    )
    assert row.created_at == T0
    assert "daftar_pilot_requests_total 1.0" in client.get("/metrics").text


def test_optional_fields(client: TestClient, db: Engine) -> None:
    body = {k: v for k, v in VALID.items() if k not in ("email", "message", "website", "lang")}
    assert client.post(URL, json=body).status_code == 202
    (row,) = _rows(db)
    assert (row.email, row.message, row.lang) == (None, "", "fr")


def test_the_honeypot_answers_202_but_stores_nothing(client: TestClient, db: Engine) -> None:
    assert client.post(URL, json={**VALID, "website": "https://spam.example"}).status_code == 202
    assert _rows(db) == []
    assert "daftar_pilot_requests_total 0.0" in client.get("/metrics").text


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"name": ""}, "validation"),
        ({"name": "x" * 121}, "validation"),
        ({"practice": "x" * 121}, "validation"),
        ({"city": ""}, "validation"),
        ({"phone": "123"}, "invalid_phone"),
        ({"email": "not-an-email"}, "validation"),
        ({"message": "x" * 2001}, "validation"),
        ({"lang": "en"}, "validation"),
        ({"website": "x" * 1001}, "validation"),
    ],
)
def test_validation(client: TestClient, db: Engine, change: dict[str, Any], code: str) -> None:
    assert_problem(client.post(URL, json={**VALID, **change}), 422, code)
    assert _rows(db) == []


def test_five_per_ip_and_hour(client: TestClient, clock: Any) -> None:
    for _ in range(5):
        assert client.post(URL, json=VALID, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 202
    res = client.post(URL, json=VALID, headers={"X-Forwarded-For": "1.2.3.4"})
    assert_problem(res, 429, "too_many_requests")
    assert int(res.headers["Retry-After"]) > 0
    assert client.post(URL, json=VALID, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 202
    clock.advance(hours=1, seconds=1)
    assert client.post(URL, json=VALID, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 202


# --- admin -----------------------------------------------------------------------------------------------------

def test_admin_lists_newest_first_and_deletes(client: TestClient, make_user: Factory, auth_headers: Factory, clock: Any) -> None:
    admin = auth_headers(make_user(role="admin"))
    client.post(URL, json={**VALID, "name": "Premier"})
    clock.advance(minutes=5)
    client.post(URL, json={**VALID, "name": "Second", "email": None})
    res = client.get("/api/admin/pilot-requests", headers=admin)
    assert res.status_code == 200, res.text
    items = res.json()
    assert [i["name"] for i in items] == ["Second", "Premier"]
    assert items[0] == {"id": items[0]["id"], "name": "Second", "practice": "Cabinet du Lac", "city": "Tunis",
                        "phone": "+21620123456", "email": None, "message": "Bonjour", "lang": "ar",
                        "createdAt": "2026-10-30T09:05:00+01:00"}
    assert client.delete(f"/api/admin/pilot-requests/{items[0]['id']}", headers=admin).status_code == 204
    assert [i["name"] for i in client.get("/api/admin/pilot-requests", headers=admin).json()] == ["Premier"]
    assert_problem(client.delete(f"/api/admin/pilot-requests/{items[0]['id']}", headers=admin), 404, "not_found")


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_only_the_admin_sees_pilot_requests(client: TestClient, make_user: Factory, auth_headers: Factory, role: str) -> None:
    h = auth_headers(make_user(role=role))
    assert_problem(client.get("/api/admin/pilot-requests", headers=h), 403, "forbidden")
    assert_problem(client.delete("/api/admin/pilot-requests/1", headers=h), 403, "forbidden")
    assert_problem(client.get("/api/admin/pilot-requests"), 401, "unauthorized")


def test_requests_older_than_twelve_months_are_deleted(db: Engine) -> None:
    with db.begin() as conn:
        for days in (366, 364):
            conn.execute(insert(pilot_request).values(name=f"{days}", practice="P", city="C", phone="+21620000000",
                                                      created_at=T0 - timedelta(days=days)))
    with db.begin() as conn:
        assert delete_old_pilot_requests(conn, T0) == 1
    assert [r.name for r in _rows(db)] == ["364"]


def test_the_cleanup_job_is_registered() -> None:
    from daftar.jobs import JOBS

    assert any(job.name == "pilot-request-cleanup" for job in JOBS)
