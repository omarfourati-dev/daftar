"""Feedback button in the app (section 15, J2): staff send, the admin reads and deletes; counter for the alert."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_staff_send_feedback(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory, role: str) -> None:
    user = make_user(make_practice("Cabinet Lac"), role, name="Sonia")
    res = client.post("/api/feedback", json={"message": "  Il manque l'impression.  ", "page": "/app/agenda"},
                      headers=auth_headers(user))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {"id": body["id"], "message": "Il manque l'impression.", "page": "/app/agenda",
                    "createdAt": "2026-10-30T09:00:00+01:00"}
    assert "daftar_feedback_total 1.0" in client.get("/metrics").text


def test_feedback_is_allowed_with_a_suspended_subscription(
    client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory
) -> None:
    user = make_user(make_practice(status="suspended"), "owner")
    assert client.post("/api/feedback", json={"message": "Je ne peux plus rien modifier"}, headers=auth_headers(user)).status_code == 201


@pytest.mark.parametrize("body", [{"message": ""}, {"message": "   "}, {"message": "x" * 2001},
                                  {"message": "ok", "page": "x" * 301}, {}])
def test_feedback_validation(client: TestClient, make_user: Factory, auth_headers: Factory, body: dict[str, Any]) -> None:
    assert_problem(client.post("/api/feedback", json=body, headers=auth_headers(make_user())), 422, "validation")


def test_feedback_needs_a_practice_account(client: TestClient, make_user: Factory, auth_headers: Factory) -> None:
    assert_problem(client.post("/api/feedback", json={"message": "x"}), 401, "unauthorized")
    assert_problem(client.post("/api/feedback", json={"message": "x"}, headers=auth_headers(make_user(role="admin"))), 403, "forbidden")


def test_feedback_is_rate_limited_per_user(client: TestClient, make_user: Factory, auth_headers: Factory, clock: Any) -> None:
    user, other = make_user(), make_user()
    for _ in range(10):
        assert client.post("/api/feedback", json={"message": "x"}, headers=auth_headers(user)).status_code == 201
    assert_problem(client.post("/api/feedback", json={"message": "x"}, headers=auth_headers(user)), 429, "too_many_requests")
    assert client.post("/api/feedback", json={"message": "x"}, headers=auth_headers(other)).status_code == 201
    clock.advance(hours=1, seconds=1)
    assert client.post("/api/feedback", json={"message": "x"}, headers=auth_headers(user)).status_code == 201


def test_admin_reads_and_deletes_feedback(
    client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory, clock: Any
) -> None:
    admin = auth_headers(make_user(role="admin"))
    lac = make_practice("Cabinet Lac")
    sonia = make_user(lac, "assistant", name="Sonia")
    client.post("/api/feedback", json={"message": "Premier", "page": "/app"}, headers=auth_headers(sonia))
    clock.advance(minutes=1)
    client.post("/api/feedback", json={"message": "Second"}, headers=auth_headers(make_user(make_practice("Cabinet B"), "owner", name="Dr B")))
    res = client.get("/api/admin/feedback", headers=admin)
    assert res.status_code == 200, res.text
    items = res.json()
    assert [i["message"] for i in items] == ["Second", "Premier"]
    assert items[1] == {"id": items[1]["id"], "practiceId": lac.id, "practiceName": "Cabinet Lac", "userId": sonia.id,
                        "userName": "Sonia", "userRole": "assistant", "message": "Premier", "page": "/app",
                        "createdAt": "2026-10-30T09:00:00+01:00"}
    assert client.delete(f"/api/admin/feedback/{items[0]['id']}", headers=admin).status_code == 204
    assert [i["message"] for i in client.get("/api/admin/feedback", headers=admin).json()] == ["Premier"]
    assert_problem(client.delete(f"/api/admin/feedback/{items[0]['id']}", headers=admin), 404, "not_found")


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_only_the_admin_reads_feedback(client: TestClient, make_user: Factory, auth_headers: Factory, role: str) -> None:
    h = auth_headers(make_user(role=role))
    assert_problem(client.get("/api/admin/feedback", headers=h), 403, "forbidden")
    assert_problem(client.delete("/api/admin/feedback/1", headers=h), 403, "forbidden")
