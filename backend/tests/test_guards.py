"""Role dependencies and router registration, exercised through a throw-away feature router."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from daftar import app as app_module
from daftar.app import create_app
from daftar.deps import AdminUser, Conn, CurrentUser, OwnerUser, PractitionerUser, StaffUser, StaffWriter
from daftar.tables import patient
from tests.conftest import TestUser
from tests.helpers import assert_problem

probe = APIRouter(prefix="/api/probe")


@probe.get("/staff")
def staff(user: StaffUser, conn: Conn) -> dict[str, Any]:
    count = conn.execute(select(func.count()).select_from(patient).where(patient.c.practice_id == user.pid)).scalar_one()
    return {"practiceId": user.pid, "patients": count}


@probe.get("/owner")
def owner(user: OwnerUser) -> dict[str, Any]:
    return {"role": user.role}


@probe.get("/practitioner")
def practitioner(user: PractitionerUser) -> dict[str, Any]:
    return {"role": user.role}


@probe.get("/admin")
def admin(user: AdminUser) -> dict[str, Any]:
    return {"role": user.role}


@probe.post("/write")
def write(user: StaffWriter) -> dict[str, Any]:
    return {"role": user.role}


@probe.get("/pid")
def pid(user: CurrentUser) -> dict[str, Any]:
    return {"pid": user.pid}


@pytest.fixture
def client(db: Any, settings: Any, clock: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(app_module, "ROUTERS", [*app_module.ROUTERS, probe])
    with TestClient(create_app(settings, clock, engine=db, run_jobs=False)) as c:
        yield c


@pytest.fixture
def headers(client: TestClient) -> Callable[[TestUser], dict[str, str]]:
    ctx = client.app.state.ctx  # type: ignore[attr-defined]
    return lambda user: {"Authorization": f"Bearer {ctx.tokens.issue(user.id, 0)}"}


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/api/probe/staff", {"owner", "dentist", "assistant"}),
        ("/api/probe/owner", {"owner"}),
        ("/api/probe/practitioner", {"owner", "dentist"}),
        ("/api/probe/admin", {"admin"}),
    ],
)
def test_roles(client: TestClient, make_user: Callable[..., TestUser], headers: Callable[..., dict[str, str]], path: str, allowed: set[str]) -> None:
    assert_problem(client.get(path), 401, "unauthorized")
    for role in ("admin", "owner", "dentist", "assistant"):
        res = client.get(path, headers=headers(make_user(role=role)))
        if role in allowed:
            assert res.status_code == 200, (role, res.text)
        else:
            assert_problem(res, 403, "forbidden")


def test_staff_queries_are_scoped_to_their_practice(
    client: TestClient,
    make_practice: Callable[..., Any],
    make_user: Callable[..., TestUser],
    make_patient: Callable[..., Any],
    headers: Callable[..., dict[str, str]],
) -> None:
    mine, other = make_practice(), make_practice()
    make_patient(mine)
    for _ in range(3):
        make_patient(other)
    res = client.get("/api/probe/staff", headers=headers(make_user(mine, "assistant")))
    assert res.json() == {"practiceId": mine.id, "patients": 1}


def test_admin_has_no_practice_id(client: TestClient, make_user: Callable[..., TestUser], headers: Callable[..., dict[str, str]]) -> None:
    assert_problem(client.get("/api/probe/pid", headers=headers(make_user(role="admin"))), 403, "forbidden")
    assert client.get("/api/probe/pid", headers=headers(make_user(role="owner"))).status_code == 200


def test_registered_routers_come_before_the_catch_alls(client: TestClient) -> None:
    # without a token: 401 from the probe, not the /api 404 or the SPA
    assert client.get("/api/probe/owner").status_code == 401


@pytest.mark.parametrize("status", ["pilot", "trial", "active", "past_due"])
def test_writes_are_allowed_unless_suspended_or_canceled(
    client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], headers: Callable[..., dict[str, str]], status: str
) -> None:
    for role in ("owner", "dentist", "assistant"):
        user = make_user(make_practice(status=status), role)
        assert client.post("/api/probe/write", headers=headers(user)).status_code == 200, (status, role)


def test_a_suspended_subscription_blocks_writes_with_402(
    client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], headers: Callable[..., dict[str, str]]
) -> None:
    user = make_user(make_practice(status="suspended"), "owner")
    body = assert_problem(client.post("/api/probe/write", headers=headers(user)), 402, "subscription_suspended")
    assert body["detail"] == "Abonnement suspendu."
    assert client.get("/api/probe/owner", headers=headers(user)).status_code == 200  # reading goes on
    assert_problem(client.post("/api/probe/write", headers=headers(make_user(role="admin"))), 403, "forbidden")


def test_a_canceled_subscription_blocks_writes_like_a_suspended_one(
    client: TestClient, make_practice: Callable[..., Any], make_user: Callable[..., TestUser], headers: Callable[..., dict[str, str]]
) -> None:
    """Security review N6: a canceled practice reads and exports its data, but changes nothing any more."""
    p = make_practice(status="canceled")
    for role in ("owner", "dentist", "assistant"):
        body = assert_problem(client.post("/api/probe/write", headers=headers(make_user(p, role))), 402, "subscription_canceled")
        assert body["detail"] == "Abonnement résilié."
    owner = make_user(p, "owner")
    assert client.get("/api/probe/owner", headers=headers(owner)).status_code == 200
    assert client.get("/api/practice/export", headers=headers(owner)).status_code == 200  # the data stays theirs
