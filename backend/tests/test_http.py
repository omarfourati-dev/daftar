"""/healthz, /metrics, /api 404, security headers, CSP, request log, error responses."""

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from daftar import app as app_module
from daftar.app import create_app
from daftar.db import make_engine
from daftar.static import inline_script_hashes
from tests.conftest import FIXTURES
from tests.helpers import assert_problem

HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def test_healthz(client: TestClient) -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_healthz_reports_a_dead_database(settings: Any, clock: Any) -> None:
    dead = make_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
    client = TestClient(create_app(settings, clock, engine=dead, run_jobs=False))  # no lifespan: no bootstrap
    assert_problem(client.get("/healthz"), 503, "database_unavailable")


def test_startup_fails_fast_without_database(settings: Any, clock: Any) -> None:
    dead = make_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
    with pytest.raises(Exception), TestClient(create_app(settings, clock, engine=dead, run_jobs=False)):
        pass  # Docker restarts the container; alembic upgrade runs before anyway


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
@pytest.mark.parametrize("path", ["/api", "/api/nope", "/api/auth/nope", "/api/x/y/z"])
def test_unknown_api_paths_are_problem_404(client: TestClient, method: str, path: str) -> None:
    body = assert_problem(client.request(method, path), 404, "not_found")
    assert body["type"] == "about:blank" and body["title"] == "Not Found"


def test_wrong_method_on_a_known_route_is_problem_405(client: TestClient) -> None:
    assert_problem(client.get("/api/auth/login"), 405, "method_not_allowed")


@pytest.mark.parametrize("path", ["/healthz", "/api/nope", "/connexion", "/", "/site.css"])
def test_security_headers_everywhere(client: TestClient, path: str) -> None:
    res = client.get(path)
    for name, value in HEADERS.items():
        assert res.headers[name] == value, (path, name)
    csp = res.headers["content-security-policy"]
    for part in [
        "default-src 'self'",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "font-src 'self'",
        "frame-ancestors 'none'",
    ]:
        assert part in csp, (path, part)
    assert "http" not in csp  # no external host anywhere


def test_csp_allows_exactly_the_inline_script_of_the_spa_shell(client: TestClient) -> None:
    html = (FIXTURES / "web" / "200.html").read_text(encoding="utf-8")
    hashes = inline_script_hashes(html)
    assert hashes == ["LVQX0/CCjy48nWgLNji9mg1tmiGdYyEEm8mqInKaYOU="]  # sha256 of "window.__boot = 1;", base64
    script_src = next(p for p in client.get("/connexion").headers["content-security-policy"].split("; ") if p.startswith("script-src"))
    assert script_src == "script-src 'self' 'sha256-LVQX0/CCjy48nWgLNji9mg1tmiGdYyEEm8mqInKaYOU='"


def test_inline_script_hashes_ignore_external_and_empty_scripts() -> None:
    assert inline_script_hashes('<script src="/a.js"></script><script type="module" src=/b.js></script><script> </script>') == []


def test_metrics_exposes_base_and_business_metrics(client: TestClient, make_practice: Any, make_user: Any, clock: Any) -> None:
    make_practice()
    make_practice(is_demo=True, demo_expires_at=clock.now())
    make_user(role="admin")
    make_user(role="owner")
    client.get("/api/auth/me")
    text = client.get("/metrics").text
    assert 'daftar_practices{kind="pilot"} 2.0' in text  # make_user created a practice for the owner
    assert 'daftar_practices{kind="demo"} 1.0' in text
    assert "daftar_users 1.0" in text  # the admin does not count
    assert "daftar_patients 0.0" in text
    assert "daftar_appointments_created_total 0.0" in text
    assert "daftar_demo_started_total 0.0" in text
    assert "daftar_pilot_requests_total 0.0" in text
    assert 'daftar_http_requests_total{method="GET",route="/api/auth/me",status="401"} 1.0' in text
    assert 'daftar_http_request_duration_seconds_count{method="GET",route="/api/auth/me"} 1.0' in text
    assert "process_" in text or "python_info" in text


def test_metrics_label_static_requests_by_kind_not_by_path(client: TestClient) -> None:
    client.get("/app/patients/42")
    client.get("/does-not-exist.js")
    text = client.get("/metrics").text
    assert 'route="static",status="200"' in text
    assert 'route="static",status="404"' in text
    assert "patients/42" not in text


def test_feature_modules_can_add_metrics(app: Any, client: TestClient) -> None:
    metrics = app.state.ctx.metrics
    counter = metrics.counter("daftar_reminders_sent_total", "Reminders marked as sent")
    assert metrics.counter("daftar_reminders_sent_total", "Reminders marked as sent") is counter
    counter.inc(2)
    metrics.gauge("daftar_queue_waiting", "People waiting").set(3)
    text = client.get("/metrics").text
    assert "daftar_reminders_sent_total 2.0" in text
    assert "daftar_queue_waiting 3.0" in text


def test_request_log_has_no_query_string_and_skips_probes(settings: Any, clock: Any, db: Any, caplog: pytest.LogCaptureFixture) -> None:
    from dataclasses import replace

    with TestClient(create_app(replace(settings, log_requests=True), clock, engine=db, run_jobs=False)) as client:
        with caplog.at_level(logging.INFO, logger="daftar.http"):
            client.get("/api/nope?token=geheim")
            client.get("/healthz")
            client.get("/metrics")
    lines = [r.getMessage() for r in caplog.records if r.name == "daftar.http"]
    assert len(lines) == 1
    assert lines[0].startswith("GET /api/nope 404 ")
    assert "geheim" not in lines[0]


boom = APIRouter()


class _Body(BaseModel):
    secret: str
    count: int


@boom.get("/api/boom")
def explode() -> None:
    raise RuntimeError("kaputt")


@boom.post("/api/echo")
def echo(body: _Body) -> dict[str, int]:
    return {"count": body.count}


@pytest.fixture
def boom_client(db: Any, settings: Any, clock: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(app_module, "ROUTERS", [*app_module.ROUTERS, boom])
    with TestClient(create_app(settings, clock, engine=db, run_jobs=False), raise_server_exceptions=False) as c:
        yield c


def test_unexpected_errors_are_problem_500_with_headers(boom_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="daftar"):
        res = boom_client.get("/api/boom")
    body = assert_problem(res, 500, "server_error")
    assert "kaputt" not in res.text
    assert body["detail"] == "Une erreur est survenue."
    assert res.headers["x-content-type-options"] == "nosniff"
    assert any("RuntimeError" in r.getMessage() for r in caplog.records)


def test_validation_errors_name_the_field_but_never_echo_values(boom_client: TestClient) -> None:
    res = boom_client.post("/api/echo", json={"secret": "streng-geheim", "count": "viele"})
    body = assert_problem(res, 422, "validation")
    assert body["errors"] == [{"field": "count", "type": "int_parsing", "message": body["errors"][0]["message"]}]
    assert "streng-geheim" not in res.text and "viele" not in res.text
    res = boom_client.post("/api/echo", content=b"{not json", headers={"Content-Type": "application/json"})
    assert_problem(res, 422, "validation")
