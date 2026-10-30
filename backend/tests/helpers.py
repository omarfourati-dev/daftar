"""Small assertions and calls shared by the API tests (import with ``from tests.helpers import ...``)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def assert_problem(res: Any, status: int, code: str) -> dict[str, Any]:
    """The response is ``application/problem+json`` with this status and ``code``; returns the body."""
    assert res.status_code == status, res.text
    assert res.headers["content-type"].startswith("application/problem+json"), res.headers["content-type"]
    body = res.json()
    assert body["status"] == status and body["code"] == code and body["title"], body
    return body


def login(client: TestClient, email: str, password: str = PASSWORD, ip: str | None = None) -> Any:
    headers = {"X-Forwarded-For": ip} if ip else {}
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers=headers)
