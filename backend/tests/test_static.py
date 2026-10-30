"""Static delivery order, caching and traversal protection (design section 2)."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from daftar.static import decode_path, is_spa_route
from tests.helpers import APP_HOST, assert_problem

SHELL_MARK = "window.__boot = 1;"
IMMUTABLE = "public, max-age=31536000, immutable"
#: The SPA runs on the app host only (fixlist 1); the main domain sends app routes there (tests/test_hosts.py).
ON_APP = {"host": APP_HOST}


def get(client: TestClient, path: str, **kw: Any) -> Any:
    return client.get(path, follow_redirects=False, **kw)


@pytest.mark.parametrize(
    ("path", "contains", "cache", "ctype"),
    [
        ("/", "Fini le cahier", "no-cache", "text/html; charset=utf-8"),
        ("/ar/", "وداعا للدفتر", "no-cache", "text/html; charset=utf-8"),
        ("/mentions-legales/", "Mentions légales", "no-cache", "text/html; charset=utf-8"),
        ("/site.css", "font-family", "no-cache", "text/css; charset=utf-8"),
        ("/robots.txt", "User-agent", "no-cache", "text/plain; charset=utf-8"),
        ("/favicon.svg", "landing", "public, max-age=86400", "image/svg+xml"),  # the landing wins over web/build
        ("/_app/immutable/entry/start.Ab1-_x9Z.js", "console.log", IMMUTABLE, "text/javascript; charset=utf-8"),
        ("/_app/version.json", '"version"', "no-cache", "application/json"),
        ("/sw.js", "BUILD", "no-cache", "text/javascript; charset=utf-8"),
        ("/manifest.webmanifest", "Daftar", "no-cache", "application/manifest+json"),
    ],
)
def test_files(client: TestClient, path: str, contains: str, cache: str, ctype: str) -> None:
    res = get(client, path)
    assert res.status_code == 200, path
    assert contains in res.text
    assert res.headers["cache-control"] == cache
    assert res.headers["content-type"] == ctype


@pytest.mark.parametrize(
    "path",
    [
        "/app",
        "/app/",
        "/app/agenda",
        "/app/patients/42",
        "/app/recu/7",
        "/connexion",
        "/invitation",
        "/reinitialiser",
        "/salle/0a1b2c3d4e",
        "/ticket/0a1b2c3d4e",
    ],
)
def test_spa_routes_get_the_shell(client: TestClient, path: str) -> None:
    res = get(client, path, headers=ON_APP)
    assert res.status_code == 200, path
    assert SHELL_MARK in res.text
    assert res.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    "path",
    [
        "/salle/",  # the display needs a token
        "/ticket",
        "/app/missing.js",  # a file extension is never the SPA
        "/connexion.php",
        "/wp-login.php",
        "/applications",  # only /app and /app/...
        "/autre-page",
    ],
)
def test_everything_else_is_404_with_the_landing_page(client: TestClient, path: str) -> None:
    res = get(client, path)
    assert res.status_code == 404, path
    assert "Page introuvable" in res.text
    assert res.headers["content-type"] == "text/html; charset=utf-8"


def test_404_without_a_landing_404_page_is_problem_json(settings: Any, clock: Any, db: Any, tmp_path: Path) -> None:
    from dataclasses import replace

    from daftar.app import create_app

    with TestClient(create_app(replace(settings, landing_dir=tmp_path), clock, engine=db, run_jobs=False)) as client:
        assert_problem(get(client, "/nothing-here"), 404, "not_found")
        assert SHELL_MARK in get(client, "/app", headers=ON_APP).text  # the SPA still works without a landing


def test_directories_without_slash_redirect(client: TestClient) -> None:
    res = get(client, "/ar")
    assert res.status_code == 308
    assert res.headers["location"] == "/ar/"
    res = get(client, "/mentions-legales?x=1")
    assert res.headers["location"] == "/mentions-legales/?x=1"


@pytest.mark.parametrize(
    "path",
    [
        "/..%2f..%2fetc/passwd",
        "/%2e%2e%2fsecret",
        "/%2e%2e/%2e%2e/backend/daftar/settings.py",
        "/app/..%2f..%2fbackend",
        "/%00x",
        "/app/%0aagenda",
        "/static%5c..%5c..%5cwindows",
        "/salle/abc%5cdef",  # a backslash is never part of a valid path
        "/C:/Windows/win.ini",
        "//etc/passwd",
    ],
)
def test_traversal_attempts_are_hard_404s(client: TestClient, path: str) -> None:
    res = get(client, path)
    assert res.status_code == 404, path
    assert SHELL_MARK not in res.text


def test_malformed_escapes() -> None:
    assert decode_path("/%zz") is None
    assert decode_path("/%") is None
    assert decode_path("/%2") is None
    assert decode_path("/%ff%fe") is None  # not UTF-8
    assert decode_path("/a%20b+c") == "/a b+c"


def test_etag_revalidation(client: TestClient) -> None:
    first = get(client, "/connexion", headers=ON_APP)
    etag = first.headers["etag"]
    again = get(client, "/connexion", headers={**ON_APP, "If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert get(client, "/", headers={"If-None-Match": etag}).status_code == 200  # another file, another tag


def test_head_requests(client: TestClient) -> None:
    res = client.head("/connexion", headers=ON_APP)
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-cache"


def test_api_paths_never_get_files(client: TestClient) -> None:
    # (``/api/../app`` cannot be tested here: the HTTP client normalizes it to ``/app`` before sending)
    assert_problem(get(client, "/api%2Fauth"), 404, "not_found")


def test_spa_route_rules() -> None:
    assert is_spa_route("/app") and is_spa_route("/invitation/") and is_spa_route("/ticket/abc")
    assert not is_spa_route("/ticket/") and not is_spa_route("/app.js") and not is_spa_route("/appointments")


def test_the_app_host_root_keeps_the_query() -> None:
    """``https://app.<BASE_DOMAIN>/?lang=ar`` opens ``/app?lang=ar`` (no database needed: StaticSite alone)."""
    from starlette.requests import Request

    from daftar.static import StaticSite
    from tests.conftest import FIXTURES

    site = StaticSite(FIXTURES / "landing", FIXTURES / "web")
    for query, location in ((b"", "/app"), (b"lang=ar", "/app?lang=ar")):
        scope = {"type": "http", "method": "GET", "path": "/", "raw_path": b"/", "query_string": query, "headers": []}
        res = site.respond_app(Request(scope), "https://daftar.omarfourati.de")
        assert (res.status_code, res.headers["location"]) == (302, location)
