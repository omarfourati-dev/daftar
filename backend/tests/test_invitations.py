"""/api/invitations/preview and /accept, the stored hash, and the cleanup of stale invitations."""

import hashlib
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.invitations import INVITATION_TTL, create_invitation
from daftar.jobs import cleanup_invitations
from daftar.tables import app_user, invitation
from tests.conftest import TestUser
from tests.helpers import assert_problem, login

ACCEPT = {"name": "Dr Karim Trabelsi", "email": "Karim@Example.TN", "password": "mot-de-passe-du-dentiste"}


def test_only_the_hash_of_the_token_is_stored(app: Any, make_practice: Callable[..., Any], clock: Any) -> None:
    p = make_practice()
    with app.state.ctx.engine.begin() as conn:
        created = create_invitation(conn, practice_id=p.id, role="dentist", created_by=None, now=clock.now())
        row = conn.execute(select(invitation)).one()
    assert len(created.token) >= 40
    assert row.token_hash == hashlib.sha256(created.token.encode()).hexdigest()
    assert created.token not in row
    assert row.expires_at == clock.now() + timedelta(days=7) == created.expires_at
    assert INVITATION_TTL == timedelta(days=7)


def test_preview_shows_practice_and_role(client: TestClient, make_practice: Callable[..., Any], make_invitation: Callable[..., str]) -> None:
    token = make_invitation(make_practice("Cabinet Dentaire Lac 2"), "assistant")
    res = client.post("/api/invitations/preview", json={"token": token})
    assert res.status_code == 200, res.text
    assert res.json() == {"practiceName": "Cabinet Dentaire Lac 2", "role": "assistant", "isDemo": False}


def test_preview_of_unknown_expired_or_used_links_is_404(
    client: TestClient, clock: Any, make_practice: Callable[..., Any], make_invitation: Callable[..., str]
) -> None:
    p = make_practice()
    assert_problem(client.post("/api/invitations/preview", json={"token": "unknown"}), 404, "invitation_invalid")
    used = make_invitation(p)
    assert client.post("/api/invitations/accept", json={"token": used, **ACCEPT}).status_code == 201
    assert_problem(client.post("/api/invitations/preview", json={"token": used}), 404, "invitation_invalid")
    expiring = make_invitation(p)
    clock.advance(days=7)
    assert_problem(client.post("/api/invitations/preview", json={"token": expiring}), 404, "invitation_invalid")


def test_accept_creates_the_account_in_the_practice_with_the_role(
    client: TestClient, app: Any, make_practice: Callable[..., Any], make_invitation: Callable[..., str], clock: Any
) -> None:
    p = make_practice("Cabinet Dentaire Sousse")
    token = make_invitation(p, "owner")
    res = client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "lang": "ar"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["user"]["email"] == "karim@example.tn"
    assert body["user"]["name"] == "Dr Karim Trabelsi"
    assert body["user"]["role"] == "owner"
    assert body["user"]["lang"] == "ar"
    assert body["user"]["practice"]["id"] == p.id
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["practice"]["name"] == "Cabinet Dentaire Sousse"
    with app.state.ctx.engine.connect() as conn:
        assert conn.execute(select(invitation.c.used_at)).scalar_one() == clock.now()
    assert login(client, "karim@example.tn", ACCEPT["password"]).status_code == 200


def test_a_link_works_only_once(client: TestClient, make_practice: Callable[..., Any], make_invitation: Callable[..., str]) -> None:
    token = make_invitation(make_practice())
    assert client.post("/api/invitations/accept", json={"token": token, **ACCEPT}).status_code == 201
    again = {**ACCEPT, "email": "autre@example.tn"}
    assert_problem(client.post("/api/invitations/accept", json={"token": token, **again}), 404, "invitation_invalid")


def test_accept_refuses_a_taken_email(
    client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], make_invitation: Callable[..., str]
) -> None:
    make_user(email="karim@example.tn")
    token = make_invitation(make_practice())
    assert_problem(client.post("/api/invitations/accept", json={"token": token, **ACCEPT}), 409, "email_taken")
    # the invitation stays usable with another address
    assert client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "email": "k2@example.tn"}).status_code == 201


def test_accept_validates_input(client: TestClient, app: Any, make_practice: Callable[..., Any], make_invitation: Callable[..., str]) -> None:
    token = make_invitation(make_practice())
    assert_problem(
        client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "password": "court"}), 422, "password_too_short"
    )
    assert_problem(
        client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "email": "pas-une-adresse"}), 422, "validation"
    )
    assert_problem(client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "name": " "}), 422, "validation")
    with app.state.ctx.engine.connect() as conn:
        assert conn.execute(select(app_user)).first() is None


def test_guessing_tokens_is_throttled_per_ip(client: TestClient, make_practice: Callable[..., Any], make_invitation: Callable[..., str]) -> None:
    token = make_invitation(make_practice())
    for i in range(5):
        client.post("/api/invitations/preview", json={"token": f"guess-{i}"}, headers={"X-Forwarded-For": "203.0.113.9"})
    res = client.post("/api/invitations/preview", json={"token": token}, headers={"X-Forwarded-For": "203.0.113.9"})
    assert_problem(res, 429, "too_many_requests")
    res = client.post("/api/invitations/preview", json={"token": token}, headers={"X-Forwarded-For": "198.51.100.2"})
    assert res.status_code == 200


def test_only_an_accepted_invitation_clears_the_counter(client: TestClient, make_practice: Callable[..., Any],
                                                       make_invitation: Callable[..., str]) -> None:
    """Security review M2: a valid preview no longer resets the counter per IP."""
    token = make_invitation(make_practice())
    for i in range(3):
        client.post("/api/invitations/preview", json={"token": f"typo-{i}"})
    assert client.post("/api/invitations/preview", json={"token": token}).status_code == 200
    assert client.post("/api/invitations/accept", json={"token": token, **ACCEPT}).status_code == 201  # 5th: clears
    for i in range(4):
        client.post("/api/invitations/preview", json={"token": f"typo-again-{i}"})
    assert client.post("/api/invitations/preview", json={"token": make_invitation(make_practice())}).status_code == 200


def test_accounts_cannot_be_probed_by_alternating_accept_and_preview(
    client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], make_invitation: Callable[..., str]
) -> None:
    """Security review M2: "e-mail taken" plus a valid preview used to reset the counter – unlimited probing."""
    token = make_invitation(make_practice())
    ip = {"X-Forwarded-For": "203.0.113.20"}
    taken = [make_user(email=f"medecin{i}@example.tn").email for i in range(3)]
    statuses = []
    for email in taken:
        statuses.append(client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "email": email}, headers=ip).status_code)
        statuses.append(client.post("/api/invitations/preview", json={"token": token}, headers=ip).status_code)
    assert statuses == [409, 200, 409, 200, 409, 429]


def test_demo_invitations_show_the_link_but_create_no_account(
    client: TestClient, app: Any, clock: Any, make_practice: Callable[..., Any], make_user: Callable[..., TestUser],
    make_invitation: Callable[..., str]
) -> None:
    """Security review M2: a demo owner (anybody) may make a link to see how it works; accepting it is refused in a
    friendly way, before the e-mail is looked at (no "e-mail taken" oracle, no squatting of addresses)."""
    demo = make_practice(is_demo=True, demo_expires_at=clock.now() + timedelta(hours=24))
    token = make_invitation(demo, "assistant")
    res = client.post("/api/invitations/preview", json={"token": token})
    assert res.status_code == 200 and res.json()["isDemo"] is True
    make_user(email="karim@example.tn")
    for email in ("karim@example.tn", "nouveau@example.tn"):
        body = assert_problem(client.post("/api/invitations/accept", json={"token": token, **ACCEPT, "email": email}),
                              403, "demo_invitation")
        assert "démo" in body["detail"]
    with app.state.ctx.engine.connect() as conn:
        assert conn.execute(select(app_user.c.id).where(app_user.c.email == "nouveau@example.tn")).first() is None
        assert conn.execute(select(invitation.c.used_at)).scalar_one() is None


def test_cleanup_job_deletes_only_stale_unused_invitations(
    app: Any, clock: Any, make_practice: Callable[..., Any], make_invitation: Callable[..., str], client: TestClient
) -> None:
    p = make_practice()
    stale = make_invitation(p)
    used = make_invitation(p)
    client.post("/api/invitations/accept", json={"token": used, **ACCEPT})
    clock.advance(days=20)
    recent = make_invitation(p)  # expires on day 27
    clock.advance(days=18)  # day 38: the first two expired 31 days ago, the recent one only 11 days ago
    cleanup_invitations(app.state.ctx)
    with app.state.ctx.engine.connect() as conn:
        left = set(conn.execute(select(invitation.c.token_hash)).scalars())
    sha = lambda t: hashlib.sha256(t.encode()).hexdigest()  # noqa: E731
    assert left == {sha(used), sha(recent)}
    assert sha(stale) not in left
