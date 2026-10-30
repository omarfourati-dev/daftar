"""The admin account from ADMIN_EMAIL / ADMIN_PASSWORD at startup."""

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.app import create_app
from daftar.settings import SettingsError
from daftar.tables import app_user
from tests.conftest import TestUser
from tests.helpers import login


def start(settings: Any, clock: Any, db: Any, **admin: Any) -> TestClient:
    client = TestClient(create_app(replace(settings, **admin), clock, engine=db, run_jobs=False))
    client.__enter__()
    return client


def test_creates_the_admin(settings: Any, clock: Any, db: Any) -> None:
    client = start(settings, clock, db, admin_email="omar@daftar.test", admin_password="admin-passwort-123")
    res = login(client, "omar@daftar.test", "admin-passwort-123")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "admin"
    assert res.json()["user"]["practice"] is None
    client.__exit__(None, None, None)


def test_keeps_a_password_changed_in_the_app(settings: Any, clock: Any, db: Any) -> None:
    first = start(settings, clock, db, admin_email="omar@daftar.test", admin_password="admin-passwort-123")
    token = login(first, "omar@daftar.test", "admin-passwort-123").json()["token"]
    first.post(
        "/api/auth/password",
        json={"current": "admin-passwort-123", "next": "neues-admin-passwort"},
        headers={"Authorization": f"Bearer {token}"},
    )
    first.__exit__(None, None, None)
    second = start(settings, clock, db, admin_email="omar@daftar.test", admin_password="admin-passwort-123")
    assert login(second, "omar@daftar.test", "neues-admin-passwort").status_code == 200
    assert login(second, "omar@daftar.test", "admin-passwort-123").status_code == 401
    second.__exit__(None, None, None)
    with db.connect() as conn:
        assert conn.execute(select(app_user.c.id).where(app_user.c.role == "admin")).all() == [(1,)]


def test_reset_password_on_request(settings: Any, clock: Any, db: Any) -> None:
    start(settings, clock, db, admin_email="omar@daftar.test", admin_password="admin-passwort-123").__exit__(None, None, None)
    client = start(
        settings, clock, db, admin_email="omar@daftar.test", admin_password="anderes-passwort-9", admin_reset_password=True
    )
    assert login(client, "omar@daftar.test", "anderes-passwort-9").status_code == 200
    client.__exit__(None, None, None)


def test_leaves_a_practice_account_alone(
    settings: Any, clock: Any, db: Any, make_user: Callable[..., TestUser], caplog: pytest.LogCaptureFixture
) -> None:
    owner = make_user(email="omar@daftar.test")
    with caplog.at_level(logging.WARNING, logger="daftar"):
        client = start(settings, clock, db, admin_email="omar@daftar.test", admin_password="admin-passwort-123")
    assert login(client, owner.email, owner.password).json()["user"]["role"] == "owner"
    assert "practice account" in caplog.text
    client.__exit__(None, None, None)


def test_refuses_a_short_admin_password(settings: Any, clock: Any, db: Any) -> None:
    with pytest.raises(SettingsError, match="ADMIN_PASSWORD"):
        start(settings, clock, db, admin_email="omar@daftar.test", admin_password="kurz")


def test_warns_when_there_is_no_admin(settings: Any, clock: Any, db: Any, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="daftar"):
        start(settings, clock, db).__exit__(None, None, None)
    assert "no admin account" in caplog.text
