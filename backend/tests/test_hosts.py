"""Practice sub-domains (sections 11.3 and 13): host routing, TLS check, login per practice, manifests and icons."""

import io
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import update

from daftar.branding import initials, short_name
from daftar.hosts import subdomain_label
from daftar.tables import practice
from tests.conftest import TestUser
from tests.helpers import assert_problem, login

BASE = "daftar.omarfourati.de"
SHELL_MARK = "window.__boot = 1;"
Factory = Callable[..., Any]


def on(host: str) -> dict[str, str]:
    return {"host": host}


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet Dentaire du Lac", slug="cabinet-lac", specialty="dentiste", brand_color="#1d4ed8")


# --- host parsing -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("host", "label"),
    [
        ("cabinet-lac.daftar.omarfourati.de", "cabinet-lac"),
        ("Cabinet-Lac.DAFTAR.omarfourati.de:443", "cabinet-lac"),
        ("cabinet-lac.daftar.omarfourati.de.", "cabinet-lac"),
        ("a.b.daftar.omarfourati.de", "a.b"),
        ("daftar.omarfourati.de", None),
        ("localhost:18083", None),
        ("testserver", None),
        ("evil-daftar.omarfourati.de", None),
        ("cabinet-lac.daftar.omarfourati.de.evil.tn", None),
        ("", None),
        (None, None),
    ],
)
def test_subdomain_label(host: str | None, label: str | None) -> None:
    assert subdomain_label(host, BASE) == label


# --- static routing on a practice sub-domain -------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", "/rdv/abc123", "/app", "/app/agenda", "/connexion", "/invitation", "/reinitialiser"])
def test_practice_host_serves_the_spa(client: TestClient, lac: Any, path: str) -> None:
    res = client.get(path, headers=on("cabinet-lac." + BASE), follow_redirects=False)
    assert res.status_code == 200, path
    assert SHELL_MARK in res.text


@pytest.mark.parametrize("path", ["/_app/immutable/entry/start.Ab1-_x9Z.js", "/sw.js", "/favicon.svg", "/_app/version.json"])
def test_practice_host_serves_app_assets(client: TestClient, lac: Any, path: str) -> None:
    assert client.get(path, headers=on("cabinet-lac." + BASE), follow_redirects=False).status_code == 200


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/mentions-legales/", f"https://{BASE}/mentions-legales/"),
        ("/ar/", f"https://{BASE}/ar/"),
        ("/site.css", f"https://{BASE}/site.css"),
        ("/salle/0a1b2c", f"https://{BASE}/salle/0a1b2c"),
        ("/autre?x=1&y=2", f"https://{BASE}/autre?x=1&y=2"),
    ],
)
def test_practice_host_redirects_the_rest_to_the_main_domain(client: TestClient, lac: Any, path: str, target: str) -> None:
    res = client.get(path, headers=on("cabinet-lac." + BASE), follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == target


@pytest.mark.parametrize("host", ["inconnu." + BASE, "www." + BASE, "a.b." + BASE, "Bad_Slug." + BASE])
def test_unknown_practice_hosts_are_404(client: TestClient, lac: Any, host: str) -> None:
    for path in ("/", "/app", "/_app/version.json", "/manifest.webmanifest"):
        res = client.get(path, headers=on(host), follow_redirects=False)
        assert res.status_code == 404, (host, path)
        assert SHELL_MARK not in res.text


def test_api_works_on_practice_hosts(client: TestClient, lac: Any) -> None:
    assert client.get("/healthz", headers=on("cabinet-lac." + BASE)).status_code == 200
    assert_problem(client.get("/api/auth/me", headers=on("cabinet-lac." + BASE)), 401, "unauthorized")


def test_main_domain_keeps_the_landing(client: TestClient, lac: Any) -> None:
    assert "Fini le cahier" in client.get("/", headers=on(BASE)).text
    assert client.get("/r/", headers=on(BASE)).status_code == 404


# --- the app on its own origin app.<BASE_DOMAIN> (fixlist 1: no token next to the ads of the main domain) ------------

APP = "app." + BASE
APP_PATHS = [
    "/app", "/app/", "/app/admin", "/app/demo", "/app/patients/42", "/connexion", "/invitation", "/reinitialiser",
    "/r/cabinet-lac", "/rdv/abc123", "/salle/0a1b2c", "/ticket/0a1b2c",
]


@pytest.mark.parametrize("path", APP_PATHS)
def test_app_host_serves_the_spa(client: TestClient, lac: Any, path: str) -> None:
    res = client.get(path, headers=on(APP), follow_redirects=False)
    assert res.status_code == 200, path
    assert SHELL_MARK in res.text
    assert res.headers["cache-control"] == "no-cache"


def test_app_host_root_opens_the_app(client: TestClient) -> None:
    res = client.get("/", headers=on(APP), follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/app"


@pytest.mark.parametrize(
    ("path", "contains"),
    [
        ("/_app/immutable/entry/start.Ab1-_x9Z.js", "console.log"),
        ("/_app/version.json", '"version"'),
        ("/sw.js", "BUILD"),
        ("/manifest.webmanifest", '"start_url":"/app"'),
        ("/favicon.svg", "<title>web</title>"),  # the app's icon, not the landing's
        ("/200.html", SHELL_MARK),
    ],
)
def test_app_host_serves_the_app_files(client: TestClient, path: str, contains: str) -> None:
    res = client.get(path, headers=on(APP), follow_redirects=False)
    assert res.status_code == 200, path
    assert contains in res.text


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ("/mentions-legales/", f"https://{BASE}/mentions-legales/"),
        ("/ar/", f"https://{BASE}/ar/"),
        ("/confidentialite/?x=1", f"https://{BASE}/confidentialite/?x=1"),
        ("/robots.txt", f"https://{BASE}/robots.txt"),
        ("/autre", f"https://{BASE}/autre"),  # the main domain shows its 404 page
        ("/r/", f"https://{BASE}/r/"),
        ("/app/missing.js", f"https://{BASE}/app/missing.js"),
    ],
)
def test_app_host_sends_the_rest_to_the_main_domain(client: TestClient, path: str, target: str) -> None:
    res = client.get(path, headers=on(APP), follow_redirects=False)
    assert res.status_code == 302, path
    assert res.headers["location"] == target


@pytest.mark.parametrize("path", ["/_app/immutable/missing.js", "/icons/missing.png"])
def test_app_host_unknown_app_files_are_404(client: TestClient, path: str) -> None:
    res = client.get(path, headers=on(APP), follow_redirects=False)
    assert res.status_code == 404, path
    assert SHELL_MARK not in res.text


@pytest.mark.parametrize("host", [BASE, "testserver"])
@pytest.mark.parametrize("path", APP_PATHS)
def test_main_domain_sends_app_paths_to_the_app_host(client: TestClient, lac: Any, host: str, path: str) -> None:
    res = client.get(path, headers=on(host), follow_redirects=False)
    assert res.status_code == 301, path
    assert res.headers["location"] == f"https://{APP}{path}"
    assert SHELL_MARK not in res.text


def test_the_redirect_keeps_query_and_encoding(client: TestClient) -> None:
    res = client.get("/connexion?lang=ar&next=%2Fapp", headers=on(BASE), follow_redirects=False)
    assert res.headers["location"] == f"https://{APP}/connexion?lang=ar&next=%2Fapp"
    res = client.get("/r/caf%C3%A9", headers=on(BASE), follow_redirects=False)
    assert res.headers["location"] == f"https://{APP}/r/caf%C3%A9"


@pytest.mark.parametrize("path", ["/200.html", "/app/missing.js", "/applications", "/r/"])
def test_main_domain_never_serves_the_app(client: TestClient, path: str) -> None:
    res = client.get(path, headers=on(BASE), follow_redirects=False)
    assert res.status_code == 404, path
    assert SHELL_MARK not in res.text


def test_main_domain_still_serves_the_service_worker_and_the_api(client: TestClient) -> None:
    assert client.get("/sw.js", headers=on(BASE)).status_code == 200  # old registrations update to the no-op worker
    assert client.get("/healthz", headers=on(BASE)).status_code == 200
    assert_problem(client.get("/api/auth/me", headers=on(BASE)), 401, "unauthorized")


def test_locally_the_app_host_keeps_scheme_and_port(settings: Any, clock: Any, db: Any) -> None:
    from dataclasses import replace

    from daftar.app import create_app

    with TestClient(create_app(replace(settings, base_domain="localhost"), clock, engine=db, run_jobs=False)) as local:
        res = local.get("/app/demo?lang=ar", headers=on("localhost:18086"), follow_redirects=False)
        assert (res.status_code, res.headers["location"]) == (301, "http://app.localhost:18086/app/demo?lang=ar")
        res = local.get("/mentions-legales/", headers=on("app.localhost:18086"), follow_redirects=False)
        assert (res.status_code, res.headers["location"]) == (302, "http://localhost:18086/mentions-legales/")
        assert SHELL_MARK in local.get("/connexion", headers=on("app.localhost:18086")).text
        assert "Fini le cahier" in local.get("/", headers=on("localhost:18086")).text


# --- TLS check for Caddy on-demand certificates -------------------------------------------------------------------------


def test_tls_check(client: TestClient, make_practice: Factory, clock: Any, lac: Any) -> None:
    make_practice(slug="demo-ab12cd34", is_demo=True, demo_expires_at=clock.now())
    make_practice(slug="cabinet-gele", status="suspended")
    make_practice(slug="cabinet-ferme", status="canceled")
    make_practice(slug="cabinet-actif", status="active")

    def check(domain: str) -> int:
        return client.get("/api/public/tls-check", params={"domain": domain}).status_code

    assert check("cabinet-lac." + BASE) == 200
    assert check("cabinet-actif." + BASE) == 200
    assert check("CABINET-LAC." + BASE.upper()) == 200
    assert check("app." + BASE) == 200  # the app's own host
    assert check("APP." + BASE.upper()) == 200
    for denied in ("demo-ab12cd34", "cabinet-gele", "cabinet-ferme", "inconnu", "www"):
        assert check(f"{denied}.{BASE}") == 404, denied
    assert check(BASE) == 404
    assert check("cabinet-lac.example.com") == 404
    assert check("") == 404
    assert client.get("/api/public/tls-check").status_code == 404


# --- login per practice -----------------------------------------------------------------------------------------------------


def test_login_on_a_practice_host_is_only_for_its_own_staff(
    client: TestClient, lac: Any, make_practice: Factory, make_user: Callable[..., TestUser]
) -> None:
    own = make_user(lac, "assistant")
    stranger = make_user(make_practice(slug="autre-cabinet"), "owner")
    admin = make_user(role="admin")
    host = on("cabinet-lac." + BASE)
    ok = client.post("/api/auth/login", json={"email": own.email, "password": own.password}, headers=host)
    assert ok.status_code == 200
    wrong = client.post("/api/auth/login", json={"email": own.email, "password": "falsch-falsch"}, headers=host).json()
    for user in (stranger, admin):
        res = client.post("/api/auth/login", json={"email": user.email, "password": user.password}, headers=host)
        assert assert_problem(res, 401, "invalid_credentials") == wrong
    # the app host accepts everybody, including the admin
    for user in (own, stranger, admin):
        assert login(client, user.email, user.password, host=APP).status_code == 200


@pytest.mark.parametrize("host", [BASE, "testserver", "www." + BASE])
def test_nobody_signs_in_on_the_main_domain(
    client: TestClient, lac: Any, make_user: Callable[..., TestUser], host: str
) -> None:
    """The main domain shows ads – no token may ever live on its origin (fixlist 1)."""
    wrong = login(client, "nobody@daftar.test", "falsch-falsch", host=APP).json()
    for user in (make_user(lac, "owner"), make_user(role="admin")):
        res = login(client, user.email, user.password, host=host)
        assert assert_problem(res, 401, "invalid_credentials") == wrong
        assert "token" not in res.text


def test_login_on_an_unknown_practice_host_fails_like_a_wrong_password(
    client: TestClient, lac: Any, make_user: Callable[..., TestUser]
) -> None:
    own = make_user(lac)
    res = client.post("/api/auth/login", json={"email": own.email, "password": own.password}, headers=on("inconnu." + BASE))
    assert_problem(res, 401, "invalid_credentials")


# --- manifests and icons ------------------------------------------------------------------------------------------------------


def test_app_manifest_of_a_practice(client: TestClient, lac: Any) -> None:
    res = client.get("/manifest.webmanifest", headers=on("cabinet-lac." + BASE))
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/manifest+json"
    assert res.headers["cache-control"] == "no-cache"
    manifest = json.loads(res.text)
    assert manifest["name"] == "Cabinet Dentaire du Lac – Daftar"
    assert manifest["short_name"] == "Lac"
    assert (manifest["start_url"], manifest["scope"], manifest["display"]) == ("/app", "/", "standalone")
    assert manifest["theme_color"] == "#1d4ed8"
    assert [(i["src"], i["sizes"], i["purpose"]) for i in manifest["icons"]] == [
        ("/icons/practice-192.png", "192x192", "any"),
        ("/icons/practice-512.png", "512x512", "any"),
        ("/icons/practice-maskable-512.png", "512x512", "maskable"),
    ]


def test_booking_manifest_of_a_practice(client: TestClient, lac: Any) -> None:
    manifest = client.get("/booking.webmanifest", headers=on("cabinet-lac." + BASE)).json()
    assert manifest["name"] == "Cabinet Dentaire du Lac – Rendez-vous"
    assert (manifest["start_url"], manifest["scope"]) == ("/", "/")
    assert manifest["id"] != client.get("/manifest.webmanifest", headers=on("cabinet-lac." + BASE)).json()["id"]


def test_main_domain_keeps_the_static_manifest(client: TestClient, lac: Any) -> None:
    assert client.get("/manifest.webmanifest", headers=on(BASE)).json()["short_name"] == "Daftar"
    assert client.get("/booking.webmanifest", headers=on(BASE)).status_code == 404


@pytest.mark.parametrize(("path", "size"), [("/icons/practice-192.png", 192), ("/icons/practice-512.png", 512), ("/icons/practice-maskable-512.png", 512)])
def test_practice_icons(client: TestClient, lac: Any, path: str, size: int) -> None:
    res = client.get(path, headers=on("cabinet-lac." + BASE))
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    image = Image.open(io.BytesIO(res.content)).convert("RGBA")
    assert image.size == (size, size)
    corner, center_left = image.getpixel((0, 0)), image.getpixel((size // 10, size // 2))
    if "maskable" in path:
        assert corner == (0x1D, 0x4E, 0xD8, 255)  # full bleed brand colour
    else:
        assert corner[3] == 0  # rounded, transparent corner
        assert center_left == (0x1D, 0x4E, 0xD8, 255)
    assert any(image.getpixel((x, size // 2))[:3] == (255, 255, 255) for x in range(size))  # white initials


def test_icons_follow_practice_changes(client: TestClient, lac: Any, db: Any) -> None:
    host = on("cabinet-lac." + BASE)
    before = client.get("/icons/practice-maskable-512.png", headers=host).content
    assert client.get("/icons/practice-maskable-512.png", headers=host).content == before
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(brand_color="#be123c"))
    after = Image.open(io.BytesIO(client.get("/icons/practice-maskable-512.png", headers=host).content)).convert("RGB")
    assert after.getpixel((0, 0)) == (0xBE, 0x12, 0x3C)


def test_unknown_icons_on_practice_hosts(client: TestClient, lac: Any) -> None:
    assert client.get("/icons/practice-64.png", headers=on("cabinet-lac." + BASE)).status_code == 404


@pytest.mark.parametrize(
    ("name", "want_initials", "want_short"),
    [
        ("Cabinet Dentaire du Lac", "L", "Lac"),
        ("Dr Leïla Ben Salah", "LS", "Leïla Ben"),
        ("Cabinet Dentaire El Menzah", "M", "El Menzah"),
        ("Clinique Pasteur", "P", "Pasteur"),
        ("Kiné Plus", "KP", "Kiné Plus"),
        ("عيادة النور", "D", "عيادة النور"),
        ("Centre Médical de la Marsa", "M", "la Marsa"),
        ("Polyclinique Les Berges du Lac Deux", "BD", "Les Berges"),
    ],
)
def test_initials_and_short_names(name: str, want_initials: str, want_short: str) -> None:
    assert initials(name) == want_initials
    assert short_name(name) == want_short
    assert len(short_name(name)) <= 12
