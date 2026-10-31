"""Migration 0005 (security review M3): every token issued before the deploy becomes invalid."""

from collections.abc import Callable
from typing import Any

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update

from daftar.tables import app_user
from tests.conftest import _alembic
from tests.helpers import login


def _versions(db: Engine) -> dict[int, int]:
    with db.connect() as conn:
        return dict(conn.execute(select(app_user.c.id, app_user.c.token_version)).all())  # type: ignore[arg-type]


def test_0005_signs_everybody_out_and_its_downgrade_changes_nothing(
    client: TestClient, db: Engine, make_practice: Callable[..., Any], make_user: Callable[..., Any]
) -> None:
    owner = make_user(make_practice(), "owner")
    admin = make_user(role="admin")
    with db.begin() as conn:
        conn.execute(update(app_user).where(app_user.c.id == admin.id).values(token_version=7))
    old = login(client, owner.email).json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 200

    with db.begin() as conn:
        command.downgrade(_alembic(conn), "0004")  # data only: nothing to undo, nothing lost
    assert _versions(db) == {owner.id: 0, admin.id: 7}
    with db.begin() as conn:
        command.upgrade(_alembic(conn), "head")
    assert _versions(db) == {owner.id: 1, admin.id: 8}  # each one up by one, whatever it was

    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    fresh = login(client, owner.email).json()["token"]  # signing in again works as before
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {fresh}"}).status_code == 200
