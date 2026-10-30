"""Team (``/api/staff``), staff invitations and password reset links (backlog A2/A3, sections 5 and 15)."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.tables import invitation, password_reset
from tests.conftest import TestUser
from tests.helpers import assert_problem, login
from tests.termine.conftest import Factory


@pytest.fixture
def team(make_practice: Factory, make_user: Factory) -> dict[str, Any]:
    p = make_practice("Cabinet Lac")
    other = make_practice()
    return {
        "practice": p,
        "other_practice": other,
        "owner": make_user(p, "owner", name="Dr Amira", email="amira@lac.tn"),
        "dentist": make_user(p, "dentist", name="Dr Karim", email="karim@lac.tn"),
        "assistant": make_user(p, "assistant", name="Salma", email="salma@lac.tn"),
        "stranger": make_user(other, "assistant", name="Ailleurs"),
    }


def test_staff_list(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    for who in ("owner", "dentist", "assistant"):
        res = client.get("/api/staff", headers=auth_headers(team[who]))
        assert res.status_code == 200, res.text
    items = res.json()
    assert [m["name"] for m in items] == ["Dr Amira", "Dr Karim", "Salma"]
    assert items[0] == {"id": team["owner"].id, "name": "Dr Amira", "email": "amira@lac.tn", "role": "owner",
                        "createdAt": "2026-10-30T09:00:00+01:00"}


def test_staff_needs_a_token_and_a_practice(client: TestClient, make_user: Factory, auth_headers: Factory) -> None:
    assert_problem(client.get("/api/staff"), 401, "unauthorized")
    assert_problem(client.get("/api/staff", headers=auth_headers(make_user(role="admin"))), 403, "forbidden")


def test_owner_changes_a_role(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    owner = auth_headers(team["owner"])
    res = client.patch(f"/api/staff/{team['assistant'].id}", json={"role": "dentist"}, headers=owner)
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "dentist"
    # the new role applies to the next request of that user (roles are read on every request)
    assert client.get("/api/auth/me", headers=auth_headers(team["assistant"])).json()["role"] == "dentist"


@pytest.mark.parametrize("role", ["owner", "admin", "boss", None])
def test_roles_that_cannot_be_given(client: TestClient, team: dict[str, Any], auth_headers: Factory, role: Any) -> None:
    res = client.patch(f"/api/staff/{team['assistant'].id}", json={"role": role}, headers=auth_headers(team["owner"]))
    assert_problem(res, 422, "validation")


def test_the_owner_cannot_change_or_remove_themselves_or_another_owner(
    client: TestClient, team: dict[str, Any], make_user: Factory, auth_headers: Factory
) -> None:
    owner = auth_headers(team["owner"])
    me = team["owner"].id
    other_owner = make_user(team["practice"], "owner")
    assert_problem(client.patch(f"/api/staff/{me}", json={"role": "assistant"}, headers=owner), 409, "self_not_allowed")
    assert_problem(client.delete(f"/api/staff/{me}", headers=owner), 409, "self_not_allowed")
    assert_problem(client.patch(f"/api/staff/{other_owner.id}", json={"role": "assistant"}, headers=owner), 409, "owner_protected")
    assert_problem(client.delete(f"/api/staff/{other_owner.id}", headers=owner), 409, "owner_protected")


def test_owner_removes_a_member_who_then_cannot_sign_in(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    gone_headers = auth_headers(team["dentist"])
    assert client.delete(f"/api/staff/{team['dentist'].id}", headers=auth_headers(team["owner"])).status_code == 204
    assert_problem(client.get("/api/auth/me", headers=gone_headers), 401, "unauthorized")
    assert login(client, team["dentist"].email).status_code == 401
    assert [m["name"] for m in client.get("/api/staff", headers=auth_headers(team["owner"])).json()] == ["Dr Amira", "Salma"]


def test_members_of_another_practice_are_404(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    owner = auth_headers(team["owner"])
    stranger = team["stranger"].id
    assert_problem(client.patch(f"/api/staff/{stranger}", json={"role": "dentist"}, headers=owner), 404, "not_found")
    assert_problem(client.delete(f"/api/staff/{stranger}", headers=owner), 404, "not_found")
    assert_problem(client.post(f"/api/staff/{stranger}/reset-link", headers=owner), 404, "not_found")


@pytest.mark.parametrize("who", ["dentist", "assistant"])
def test_only_the_owner_manages_the_team(client: TestClient, team: dict[str, Any], auth_headers: Factory, who: str) -> None:
    h = auth_headers(team[who])
    target = team["assistant" if who == "dentist" else "dentist"].id
    assert_problem(client.patch(f"/api/staff/{target}", json={"role": "dentist"}, headers=h), 403, "forbidden")
    assert_problem(client.delete(f"/api/staff/{target}", headers=h), 403, "forbidden")
    assert_problem(client.post(f"/api/staff/{target}/reset-link", headers=h), 403, "forbidden")
    assert_problem(client.get("/api/staff/invitations", headers=h), 403, "forbidden")
    assert_problem(client.post("/api/staff/invitations", json={"role": "assistant"}, headers=h), 403, "forbidden")


def test_a_suspended_practice_cannot_change_its_team(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice(status="suspended")
    owner, member = make_user(p, "owner"), make_user(p, "assistant")
    h = auth_headers(owner)
    assert client.get("/api/staff", headers=h).status_code == 200
    assert_problem(client.patch(f"/api/staff/{member.id}", json={"role": "dentist"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/staff/{member.id}", headers=h), 402, "subscription_suspended")
    assert_problem(client.post("/api/staff/invitations", json={"role": "dentist"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.post(f"/api/staff/{member.id}/reset-link", headers=h), 402, "subscription_suspended")


# --- invitations --------------------------------------------------------------------------------------------------


def test_owner_invites_and_the_link_works(client: TestClient, team: dict[str, Any], auth_headers: Factory, clock: Any) -> None:
    owner = auth_headers(team["owner"])
    res = client.post("/api/staff/invitations", json={"role": "assistant"}, headers=owner)
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["token"]) >= 40 and body["expiresAt"] == "2026-11-06T09:00:00+01:00"
    assert client.post("/api/invitations/preview", json={"token": body["token"]}).json() == {
        "practiceName": "Cabinet Lac", "role": "assistant"}
    listed = client.get("/api/staff/invitations", headers=owner).json()
    assert listed == [{"id": body["id"], "role": "assistant", "createdAt": "2026-10-30T09:00:00+01:00",
                       "expiresAt": "2026-11-06T09:00:00+01:00"}]


def test_invitation_list_shows_only_open_staff_invitations(
    client: TestClient, team: dict[str, Any], auth_headers: Factory, make_invitation: Factory, clock: Any
) -> None:
    p = team["practice"]
    owner = auth_headers(team["owner"])
    used = make_invitation(p, "dentist")
    client.post("/api/invitations/accept", json={"token": used, "name": "Dr X", "email": "x@lac.tn", "password": "mot-de-passe-long"})
    make_invitation(p, "owner")  # the admin's owner link is not the owner's business
    make_invitation(team["other_practice"], "dentist")  # another practice
    old = client.post("/api/staff/invitations", json={"role": "dentist"}, headers=owner).json()
    clock.advance(days=7, seconds=1)
    fresh = client.post("/api/staff/invitations", json={"role": "assistant"}, headers=owner).json()
    assert [i["id"] for i in client.get("/api/staff/invitations", headers=owner).json()] == [fresh["id"]]
    assert old["id"] != fresh["id"]


@pytest.mark.parametrize("role", ["owner", "admin", "", None])
def test_invitation_roles(client: TestClient, team: dict[str, Any], auth_headers: Factory, role: Any) -> None:
    res = client.post("/api/staff/invitations", json={"role": role}, headers=auth_headers(team["owner"]))
    assert_problem(res, 422, "validation")


def test_owner_revokes_an_invitation(client: TestClient, team: dict[str, Any], auth_headers: Factory, make_invitation: Factory, db: Any) -> None:
    owner = auth_headers(team["owner"])
    made = client.post("/api/staff/invitations", json={"role": "dentist"}, headers=owner).json()
    assert client.delete(f"/api/staff/invitations/{made['id']}", headers=owner).status_code == 204
    assert_problem(client.post("/api/invitations/preview", json={"token": made["token"]}), 404, "invitation_invalid")
    assert_problem(client.delete(f"/api/staff/invitations/{made['id']}", headers=owner), 404, "not_found")
    make_invitation(team["other_practice"], "dentist")
    make_invitation(team["practice"], "owner")
    with db.connect() as conn:
        foreign, owner_link = conn.execute(select(invitation.c.id).order_by(invitation.c.id)).scalars().all()
    assert_problem(client.delete(f"/api/staff/invitations/{foreign}", headers=owner), 404, "not_found")
    assert_problem(client.delete(f"/api/staff/invitations/{owner_link}", headers=owner), 404, "not_found")


# --- reset links ---------------------------------------------------------------------------------------------------


def _reset_link(client: TestClient, owner: TestUser, member: TestUser, auth_headers: Factory) -> dict[str, Any]:
    res = client.post(f"/api/staff/{member.id}/reset-link", headers=auth_headers(owner))
    assert res.status_code == 201, res.text
    return res.json()


def test_owner_creates_a_reset_link_and_only_its_hash_is_stored(
    client: TestClient, team: dict[str, Any], auth_headers: Factory, db: Any
) -> None:
    link = _reset_link(client, team["owner"], team["assistant"], auth_headers)
    assert len(link["token"]) >= 40 and link["expiresAt"] == "2026-10-31T09:00:00+01:00"
    with db.connect() as conn:
        row = conn.execute(select(password_reset)).one()
    assert row.token_hash == hashlib.sha256(link["token"].encode()).hexdigest()
    assert (row.user_id, row.created_by) == (team["assistant"].id, team["owner"].id)
    assert link["token"] not in str(tuple(row))


def test_reset_links_not_for_oneself_or_owners(client: TestClient, team: dict[str, Any], make_user: Factory, auth_headers: Factory) -> None:
    owner = auth_headers(team["owner"])
    assert_problem(client.post(f"/api/staff/{team['owner'].id}/reset-link", headers=owner), 409, "self_not_allowed")
    other_owner = make_user(team["practice"], "owner")
    assert_problem(client.post(f"/api/staff/{other_owner.id}/reset-link", headers=owner), 409, "owner_protected")


def test_preview_and_accept_a_reset_link(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    member = team["assistant"]
    old_headers = auth_headers(member)
    link = _reset_link(client, team["owner"], member, auth_headers)
    res = client.post("/api/password-reset/preview", json={"token": link["token"]})
    assert res.status_code == 200, res.text
    assert res.json() == {"email": "salma@lac.tn", "practiceName": "Cabinet Lac"}
    res = client.post("/api/password-reset/accept", json={"token": link["token"], "password": "nouveau-mot-de-passe"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["id"] == member.id and body["user"]["email"] == "salma@lac.tn"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"}).status_code == 200
    assert_problem(client.get("/api/auth/me", headers=old_headers), 401, "unauthorized")  # every old session ends
    assert login(client, member.email, "nouveau-mot-de-passe").status_code == 200
    assert login(client, member.email).status_code == 401


def test_a_reset_link_works_only_once(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    link = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    assert client.post("/api/password-reset/accept", json={"token": link["token"], "password": "premier-mot-de-passe"}).status_code == 200
    again = client.post("/api/password-reset/accept", json={"token": link["token"], "password": "second-mot-de-passe"})
    assert_problem(again, 404, "reset_invalid")
    assert_problem(client.post("/api/password-reset/preview", json={"token": link["token"]}), 404, "reset_invalid")
    assert login(client, team["dentist"].email, "premier-mot-de-passe").status_code == 200


def test_an_expired_reset_link_fails(client: TestClient, team: dict[str, Any], auth_headers: Factory, clock: Any) -> None:
    link = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    clock.advance(hours=24)
    assert_problem(client.post("/api/password-reset/preview", json={"token": link["token"]}), 404, "reset_invalid")
    res = client.post("/api/password-reset/accept", json={"token": link["token"], "password": "nouveau-mot-de-passe"})
    assert_problem(res, 404, "reset_invalid")


def test_a_new_reset_link_replaces_the_previous_one(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    first = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    second = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    assert_problem(client.post("/api/password-reset/preview", json={"token": first["token"]}), 404, "reset_invalid")
    assert client.post("/api/password-reset/preview", json={"token": second["token"]}).status_code == 200


def test_reset_accept_checks_the_password(client: TestClient, team: dict[str, Any], auth_headers: Factory) -> None:
    link = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    res = client.post("/api/password-reset/accept", json={"token": link["token"], "password": "court"})
    assert_problem(res, 422, "password_too_short")
    assert client.post("/api/password-reset/preview", json={"token": link["token"]}).status_code == 200  # still usable


def test_wrong_reset_tokens_are_throttled_per_ip(client: TestClient) -> None:
    ip = {"X-Forwarded-For": "198.51.100.9"}
    for _ in range(5):
        assert_problem(client.post("/api/password-reset/preview", json={"token": "faux"}, headers=ip), 404, "reset_invalid")
    assert_problem(client.post("/api/password-reset/preview", json={"token": "faux"}, headers=ip), 429, "too_many_requests")
    res = client.post("/api/password-reset/accept", json={"token": "faux", "password": "nouveau-mot-de-passe"}, headers=ip)
    assert_problem(res, 429, "too_many_requests")
    other = {"X-Forwarded-For": "198.51.100.10"}
    assert_problem(client.post("/api/password-reset/preview", json={"token": "faux"}, headers=other), 404, "reset_invalid")


def test_reset_validation(client: TestClient) -> None:
    assert_problem(client.post("/api/password-reset/preview", json={}), 422, "validation")
    assert_problem(client.post("/api/password-reset/accept", json={"token": "x"}), 422, "validation")
    assert_problem(client.post("/api/password-reset/preview", json={"token": "x" * 201}), 422, "validation")


def test_reset_link_lifetime(client: TestClient, team: dict[str, Any], auth_headers: Factory, clock: Any) -> None:
    link = _reset_link(client, team["owner"], team["dentist"], auth_headers)
    clock.advance(hours=23, minutes=59)
    assert client.post("/api/password-reset/preview", json={"token": link["token"]}).status_code == 200
