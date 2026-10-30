"""Demo practices (sections 5, 12, 15): one per visitor, filled with invented data, throttled, deleted after 24 h."""

from collections import Counter
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from daftar import demo as demo_module
from daftar.catalog import DEFAULT_CATALOGS, SPECIALTIES
from daftar.clock import TUNIS, today_tunis
from daftar.demo import delete_expired_demos
from daftar.tables import app_user, appointment, patient, payment, practice, practitioner, queue_entry, service, treatment
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]


def start(client: TestClient, ip: str = "10.0.0.1", **body: Any) -> Any:
    return client.post("/api/demo", json=body, headers={"X-Forwarded-For": ip})


def _all(db: Engine, table: Any, practice_id: int) -> list[Any]:
    with db.connect() as conn:
        return conn.execute(select(table).where(table.c.practice_id == practice_id)).all()


def test_start_returns_a_session_of_a_new_demo_practice(client: TestClient, db: Engine) -> None:
    res = start(client)
    assert res.status_code == 201, res.text
    body = res.json()
    user = body["user"]
    assert user["role"] == "owner" and user["lang"] == "fr"
    assert user["email"].startswith("demo-") and user["email"].endswith("@demo.daftar.invalid")
    brief = user["practice"]
    assert brief["isDemo"] is True and brief["specialty"] == "generaliste"
    assert brief["slug"].startswith("demo-") and len(brief["slug"]) == 13
    assert brief["demoExpiresAt"] == "2026-10-31T09:00:00+01:00"
    assert brief["name"] == "Cabinet Médical Démo"
    headers = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["id"] == user["id"]
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    assert "daftar_demo_started_total 1.0" in client.get("/metrics").text


def test_demo_data_is_realistic_and_invented(client: TestClient, db: Engine) -> None:
    body = start(client).json()
    pid = body["user"]["practice"]["id"]
    patients = _all(db, patient, pid)
    assert len(patients) == 25
    phones = {p.phone for p in patients}
    assert all(phone.startswith("+21600000") for phone in phones)  # the prefix 00 does not exist in Tunisia
    assert phones <= {f"+21600000{n:03d}" for n in range(1, 26)}
    assert len(phones) < 25  # a family shares one number
    assert sum(1 for p in patients if p.alerts) >= 2
    with db.connect() as conn:
        p = conn.execute(select(practice).where(practice.c.id == pid)).one()
    assert "00 000 000" in p.phone and p.is_demo

    appts = _all(db, appointment, pid)
    today = today_tunis(type("C", (), {"now": staticmethod(lambda: T0)})())
    days = {a.starts_at.astimezone(TUNIS).date() for a in appts}
    assert min(days) >= today - timedelta(days=14) and max(days) <= today + timedelta(days=7)
    assert today - timedelta(days=14) in days or today - timedelta(days=13) in days
    assert today + timedelta(days=1) in days  # tomorrow: reminders
    statuses = Counter(a.status for a in appts)
    for status in ("done", "no_show", "cancelled", "scheduled", "confirmed", "requested", "arrived", "in_treatment"):
        assert statuses[status] > 0, status
    assert all(a.source == "online" for a in appts if a.status == "requested")
    assert all(a.practitioner_id is not None for a in appts)
    past = [a for a in appts if a.ends_at <= T0]
    assert all(a.status in ("done", "no_show", "cancelled") for a in past if a.starts_at.astimezone(TUNIS).date() < today)
    future = [a for a in appts if a.starts_at.astimezone(TUNIS).date() > today]
    assert all(a.status in ("scheduled", "confirmed", "requested", "cancelled") for a in future)
    no_shows = Counter(a.patient_id for a in appts if a.status == "no_show")
    assert any(n >= 2 for n in no_shows.values())  # "Acompte conseillé"

    queue = _all(db, queue_entry, pid)
    q = Counter(e.status for e in queue if e.day == today)
    assert (q["waiting"], q["in_treatment"]) == (3, 1)
    assert sorted(e.ticket_no for e in queue) == list(range(1, len(queue) + 1))

    treatments, payments = _all(db, treatment, pid), _all(db, payment, pid)
    assert treatments and payments
    assert all(t.price_millimes > 0 for t in treatments) and all(pay.amount_millimes > 0 for pay in payments)
    dues = Counter()
    for t in treatments:
        dues[t.patient_id] += t.price_millimes
    for pay in payments:
        dues[pay.patient_id] -= pay.amount_millimes
    assert any(v > 0 for v in dues.values())  # instalments still open
    assert any(pay.is_deposit and pay.appointment_id for pay in payments)
    assert any(pay.paid_at.astimezone(TUNIS).date() == today for pay in payments)  # cash of today

    services = _all(db, service, pid)
    assert [s.name_fr for s in sorted(services, key=lambda s: s.sort)] == [i.name_fr for i in DEFAULT_CATALOGS["generaliste"]]
    assert all(s.price_millimes and s.price_millimes % 1000 == 0 for s in services)


@pytest.mark.parametrize("specialty", SPECIALTIES)
def test_every_specialty_gets_its_catalog(client: TestClient, db: Engine, specialty: str) -> None:
    res = start(client, specialty=specialty)
    assert res.status_code == 201, res.text
    pid = res.json()["user"]["practice"]["id"]
    assert res.json()["user"]["practice"]["specialty"] == specialty
    names = {s.name_fr for s in _all(db, service, pid)}
    assert names == {i.name_fr for i in DEFAULT_CATALOGS[specialty]}
    appts = _all(db, appointment, pid)
    assert appts and {a.reason for a in appts} <= names
    series = Counter(a.series_id for a in appts if a.series_id is not None)
    if specialty in ("kinesitherapeute", "psychologue"):
        assert len(series) >= 2 and all(n >= 3 for n in series.values())
    else:
        assert not series


def test_dentist_demo_has_teeth_and_a_treatment_plan(client: TestClient, db: Engine) -> None:
    pid = start(client, specialty="dentiste").json()["user"]["practice"]["id"]
    treatments = _all(db, treatment, pid)
    assert any(t.tooth for t in treatments)
    assert any(t.price_millimes >= 300_000 for t in treatments)


def test_arabic_demo(client: TestClient, db: Engine) -> None:
    body = start(client, lang="ar", specialty="pediatre").json()
    assert body["user"]["lang"] == "ar"
    pid = body["user"]["practice"]["id"]
    with db.connect() as conn:
        p = conn.execute(select(practice).where(practice.c.id == pid)).one()
    assert p.name_ar
    patients = _all(db, patient, pid)
    assert all(any("؀" <= ch <= "ۿ" for ch in pat.last_name) for pat in patients)
    assert Counter(pat.lang for pat in patients)["ar"] > 12


@pytest.mark.parametrize("body", [{"lang": "de"}, {"specialty": "veterinaire"}])
def test_validation(client: TestClient, body: dict[str, Any]) -> None:
    assert_problem(start(client, **body), 422, "validation")


def test_five_demos_per_ip_and_hour(client: TestClient, clock: Any) -> None:
    for _ in range(5):
        assert start(client, ip="1.2.3.4").status_code == 201
    res = start(client, ip="1.2.3.4")
    assert_problem(res, 429, "too_many_requests")
    assert res.headers["Retry-After"]
    assert start(client, ip="5.6.7.8").status_code == 201
    clock.advance(hours=1, seconds=1)
    assert start(client, ip="1.2.3.4").status_code == 201


def test_global_daily_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch, clock: Any) -> None:
    monkeypatch.setattr(demo_module, "GLOBAL_PER_DAY", 2)
    assert start(client, ip="1.1.1.1").status_code == 201
    assert start(client, ip="2.2.2.2").status_code == 201
    assert_problem(start(client, ip="3.3.3.3"), 429, "too_many_requests")
    clock.advance(days=1, seconds=1)
    assert start(client, ip="3.3.3.3").status_code == 201


def test_an_expired_demo_ends_the_session_and_is_deleted(
    client: TestClient, db: Engine, clock: Any, make_practice: Factory
) -> None:
    body = start(client).json()
    pid = body["user"]["practice"]["id"]
    keep = make_practice()  # a real practice is never touched
    fresh = make_practice(is_demo=True, demo_expires_at=T0 + timedelta(days=2))
    clock.advance(hours=24, seconds=1)
    assert_problem(client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"}), 401, "demo_expired")
    with db.begin() as conn:
        assert delete_expired_demos(conn, clock.now()) == 1
    with db.connect() as conn:
        left = {r.id for r in conn.execute(select(practice.c.id))}
        assert left == {keep.id, fresh.id}
        for table in (patient, appointment, payment, treatment, queue_entry, service, practitioner):
            assert conn.execute(select(func.count()).select_from(table).where(table.c.practice_id == pid)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(app_user).where(app_user.c.practice_id == pid)).scalar_one() == 0


def test_the_demo_cleanup_job_is_registered() -> None:
    from daftar.jobs import JOBS

    job = next(job for job in JOBS if job.name == "demo-cleanup")
    assert job.every == timedelta(minutes=30)
