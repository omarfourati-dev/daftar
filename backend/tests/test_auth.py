"""/api/auth/*: login, throttle, me, password, logout everywhere, demo expiry."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from daftar.tables import app_user, practice
from tests.conftest import PASSWORD, TestUser
from tests.helpers import assert_problem, login


def test_login_returns_token_and_me(client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser]) -> None:
    p = make_practice("Cabinet Dentaire El Menzah", slug="el-menzah", specialty="dentiste", brand_color="#1d4ed8")
    user = make_user(p, "dentist", email="Dr.Amira@Example.tn", name="Dr Amira", lang="ar")
    res = login(client, "  DR.AMIRA@example.TN ")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"] == {
        "id": user.id,
        "email": "dr.amira@example.tn",
        "name": "Dr Amira",
        "role": "dentist",
        "lang": "ar",
        "practice": {
            "id": p.id,
            "name": "Cabinet Dentaire El Menzah",
            "slug": "el-menzah",
            "specialty": "dentiste",
            "status": "pilot",
            "brandColor": "#1d4ed8",
            "isDemo": False,
            "demoExpiresAt": None,
        },
    }
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json() == body["user"]


def test_admin_has_no_practice(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    admin = make_user(role="admin", email="omar@daftar.test")
    body = login(client, admin.email).json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["practice"] is None


def test_wrong_password_and_unknown_email_are_the_same_401(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    wrong = assert_problem(login(client, user.email, "falsches-passwort"), 401, "invalid_credentials")
    unknown = assert_problem(login(client, "nobody@daftar.test"), 401, "invalid_credentials")
    assert wrong == unknown
    assert wrong["detail"] == "E-mail ou mot de passe incorrect."


def test_throttle_after_five_failures_per_email_and_ip(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    for _ in range(5):
        assert login(client, user.email, "falsch-falsch", ip="203.0.113.7").status_code == 401
    # even the right password is refused now, from this IP …
    assert_problem(login(client, user.email, ip="203.0.113.7"), 429, "too_many_requests")
    # … but not from another one
    assert login(client, user.email, ip="198.51.100.1").status_code == 200


def test_throttle_uses_the_last_forwarded_for_entry(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    for i in range(5):
        # the client controls the first entries; Caddy appends the real IP last
        login(client, user.email, "falsch-falsch", ip=f"10.0.0.{i}, 203.0.113.7")
    assert login(client, user.email, ip="10.9.9.9, 203.0.113.7").status_code == 429
    assert login(client, user.email, ip="203.0.113.7, 198.51.100.1").status_code == 200


def test_throttle_window_passes(client: TestClient, clock: Any, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    for _ in range(5):
        login(client, user.email, "falsch-falsch")
    assert login(client, user.email).status_code == 429
    clock.advance(minutes=15)
    assert login(client, user.email).status_code == 200


def test_ten_failures_lock_the_account_from_every_ip_without_telling_whether_it_exists(
    client: TestClient, clock: Any, make_user: Callable[..., TestUser]
) -> None:
    """Security review M4: a botnet has many IPs – after 10 failed logins of an e-mail in 15 minutes, every login of
    it is refused, the right password too, until the window passes. Unknown e-mails behave exactly the same."""
    user = make_user()
    for i in range(10):
        assert login(client, user.email, "falsch-falsch", ip=f"203.0.113.{i + 1}").status_code == 401
        assert login(client, "personne@daftar.test", "falsch-falsch", ip=f"198.51.100.{i + 1}").status_code == 401
    locked = login(client, user.email, ip="192.0.2.50")  # the right password, from a fresh IP
    unknown = login(client, "personne@daftar.test", ip="192.0.2.51")
    assert assert_problem(locked, 429, "too_many_requests") == assert_problem(unknown, 429, "too_many_requests")
    assert locked.headers["Retry-After"] == unknown.headers["Retry-After"]
    assert login(client, make_user().email, ip="192.0.2.50").status_code == 200  # other accounts are not touched
    clock.advance(minutes=15)
    assert login(client, user.email, ip="192.0.2.50").status_code == 200


def test_a_successful_login_clears_the_failures_of_the_account(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    for i in range(9):
        login(client, user.email, "falsch-falsch", ip=f"203.0.113.{i + 1}")
    assert login(client, user.email, ip="192.0.2.1").status_code == 200
    for i in range(9):
        login(client, user.email, "falsch-falsch", ip=f"198.51.100.{i + 1}")
    assert login(client, user.email, ip="192.0.2.2").status_code == 200


def test_login_validation_is_422_without_echoing_the_password(client: TestClient) -> None:
    res = client.post("/api/auth/login", json={"email": "a@b.tn"})
    body = assert_problem(res, 422, "validation")
    assert body["errors"][0]["field"] == "password"
    res = client.post("/api/auth/login", json={"email": "a@b.tn", "password": "geheimes-passwort" * 100})
    assert res.status_code == 422
    assert "geheimes-passwort" not in res.text


def test_login_metrics(client: TestClient, make_user: Callable[..., TestUser]) -> None:
    user = make_user()
    login(client, user.email)
    login(client, user.email, "falsch-falsch")
    text = client.get("/metrics").text
    assert 'daftar_logins_total{result="ok"} 1.0' in text
    assert 'daftar_logins_total{result="failed"} 1.0' in text
    assert 'daftar_logins_total{result="throttled"} 0.0' in text


def test_me_needs_a_valid_token(client: TestClient, clock: Any, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    assert_problem(client.get("/api/auth/me"), 401, "unauthorized")
    assert_problem(client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}), 401, "unauthorized")
    assert_problem(client.get("/api/auth/me", headers={"Authorization": "Basic abc"}), 401, "unauthorized")
    headers = auth_headers(make_user())
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    clock.advance(days=30)
    assert_problem(client.get("/api/auth/me", headers=headers), 401, "unauthorized")


def test_deleted_user_loses_access(client: TestClient, app: Any, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    user = make_user()
    headers = auth_headers(user)
    with app.state.ctx.engine.begin() as conn:
        conn.execute(app_user.delete().where(app_user.c.id == user.id))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_patch_me(client: TestClient, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    headers = auth_headers(make_user(name="Avant"))
    res = client.patch("/api/auth/me", json={"name": "  Leïla Ben Salah ", "lang": "ar"}, headers=headers)
    assert res.status_code == 200, res.text
    assert (res.json()["name"], res.json()["lang"]) == ("Leïla Ben Salah", "ar")
    res = client.patch("/api/auth/me", json={"lang": "fr"}, headers=headers)
    assert (res.json()["name"], res.json()["lang"]) == ("Leïla Ben Salah", "fr")
    assert_problem(client.patch("/api/auth/me", json={"lang": "de"}, headers=headers), 422, "validation")
    assert_problem(client.patch("/api/auth/me", json={"name": "   "}, headers=headers), 422, "validation")
    assert_problem(client.patch("/api/auth/me", json={"name": "x" * 121}, headers=headers), 422, "validation")


def test_change_password(client: TestClient, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    user = make_user()
    old = auth_headers(user)
    assert_problem(
        client.post("/api/auth/password", json={"current": "falsch-falsch", "next": "nouveau-mot-de-passe"}, headers=old),
        400,
        "wrong_password",
    )
    assert_problem(
        client.post("/api/auth/password", json={"current": PASSWORD, "next": "court"}, headers=old),
        422,
        "password_too_short",
    )
    for weak, code in (("azertyuiop", "password_sequence"), ("zzzzzzzzzzzz", "password_repeated"),
                       (f"{user.email.split('@')[0]}-2026", "password_contains_email")):
        assert_problem(client.post("/api/auth/password", json={"current": PASSWORD, "next": weak}, headers=old), 422, code)
    res = client.post("/api/auth/password", json={"current": PASSWORD, "next": "nouveau-mot-de-passe"}, headers=old)
    assert res.status_code == 200, res.text
    new = {"Authorization": f"Bearer {res.json()['token']}"}
    assert client.get("/api/auth/me", headers=new).status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401  # other sessions end
    assert login(client, user.email).status_code == 401
    assert login(client, user.email, "nouveau-mot-de-passe").status_code == 200


def test_password_guessing_is_throttled(client: TestClient, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    headers = auth_headers(make_user())
    for _ in range(5):
        client.post("/api/auth/password", json={"current": "falsch-falsch", "next": "nouveau-mot-de-passe"}, headers=headers)
    res = client.post("/api/auth/password", json={"current": PASSWORD, "next": "nouveau-mot-de-passe"}, headers=headers)
    assert_problem(res, 429, "too_many_requests")


def test_logout_everywhere(client: TestClient, make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    user = make_user()
    first, second = auth_headers(user), login(client, user.email).json()["token"]
    res = client.post("/api/auth/logout-all", headers=first)
    assert res.status_code == 204 and res.content == b""
    assert client.get("/api/auth/me", headers=first).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 401
    assert login(client, user.email).status_code == 200  # a new login works


def test_expired_demo_sessions_end(client: TestClient, app: Any, clock: Any, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], auth_headers: Callable[..., dict[str, str]]) -> None:
    demo = make_practice("Cabinet Dentaire Démo", is_demo=True, demo_expires_at=clock.now() + timedelta(hours=24))
    headers = auth_headers(make_user(demo))
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["practice"]["isDemo"] is True
    assert me["practice"]["demoExpiresAt"] == "2026-10-31T09:00:00+01:00"
    clock.advance(hours=24)
    assert_problem(client.get("/api/auth/me", headers=headers), 401, "demo_expired")
    with app.state.ctx.engine.begin() as conn:  # sanity: the practice still exists, only the session ended
        assert conn.execute(select(practice.c.id).where(practice.c.id == demo.id)).first() is not None
        conn.execute(update(practice).where(practice.c.id == demo.id).values(demo_expires_at=clock.now() + timedelta(hours=1)))
    assert client.get("/api/auth/me", headers=headers).status_code == 200
