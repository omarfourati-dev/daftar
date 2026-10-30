"""Recurring appointments (backlog B4, section 15): preview, create (skip or refuse conflicts), cancel from a day."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from daftar import scheduling
from daftar.tables import appointment
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, TUE, Factory, at, iso


@pytest.fixture
def kine(make_practice: Factory) -> Any:
    return make_practice("Cabinet Kiné", specialty="kinesitherapeute", practitioners=["Mme A", "M. B"])


@pytest.fixture
def amira(kine: Any, make_patient: Factory) -> Any:
    return make_patient(kine, first_name="Amira", last_name="Ben Ali")


def series_body(kine: Any, amira: Any, **override: Any) -> dict[str, Any]:
    body = {"patientId": amira.id, "startsAt": iso(MON, "09:00"), "durationMin": 45, "practitionerId": kine.practitioners[0].id,
            "reason": "Rééducation genou", "notes": "Ordonnance du Dr X", "rule": {"weekdays": [1], "count": 4}}
    body.update(override)
    return body


def preview(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> list[dict[str, Any]]:
    res = client.post("/api/appointments/series/preview", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["occurrences"]


def test_weekly_preview(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    occ = preview(client, as_user(kine, "assistant"), series_body(kine, amira))
    assert occ == [
        {"startsAt": iso(date(2026, 11, d), "09:00"), "endsAt": iso(date(2026, 11, d), "09:45"), "conflict": None, "closed": False}
        for d in (2, 9, 16, 23)
    ]


def test_twice_a_week_across_the_month_end(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    body = series_body(kine, amira, startsAt=iso(date(2026, 11, 23), "09:00"), rule={"weekdays": [4, 1, 1], "count": 5})
    starts = [o["startsAt"][:10] for o in preview(client, as_user(kine, "assistant"), body)]
    assert starts == ["2026-11-23", "2026-11-26", "2026-11-30", "2026-12-03", "2026-12-07"]


def test_the_series_starts_on_the_first_matching_weekday(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    body = series_body(kine, amira, startsAt=iso(TUE, "10:00"), rule={"weekdays": [1], "count": 2})
    assert [o["startsAt"] for o in preview(client, as_user(kine, "assistant"), body)] == [
        iso(date(2026, 11, 9), "10:00"), iso(date(2026, 11, 16), "10:00")]


def test_preview_shows_conflicts_and_closed_days(
    client: TestClient, kine: Any, amira: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    karim = make_patient(kine, first_name="Karim", last_name="Trabelsi")
    taken = make_appointment(karim, practitioner_id=kine.practitioners[0].id, starts_at=at(date(2026, 11, 9), "09:30"))
    owner = as_user(kine, "owner")
    client.post("/api/closures", json={"startsOn": "2026-11-16", "label": "Formation"}, headers=owner)
    occ = preview(client, owner, series_body(kine, amira))
    assert [o["closed"] for o in occ] == [False, False, True, False]
    assert occ[1]["conflict"] == {"id": taken.id, "startsAt": iso(date(2026, 11, 9), "09:30"),
                                  "endsAt": iso(date(2026, 11, 9), "10:00"), "patientName": "Karim Trabelsi"}
    assert [o["conflict"] is None for o in occ] == [True, False, True, True]
    sundays = preview(client, owner, series_body(kine, amira, rule={"weekdays": [7], "count": 2}))
    assert [o["closed"] for o in sundays] == [True, True]  # no opening hours on Sunday
    lunch = preview(client, owner, series_body(kine, amira, startsAt=iso(MON, "12:00")))
    assert all(o["closed"] for o in lunch)  # 12:00 + 45 min runs into the lunch break


def test_create_a_series(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    res = client.post("/api/appointments/series", json=series_body(kine, amira), headers=as_user(kine, "assistant"))
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["seriesId"]) == 36 and body["skipped"] == []
    created = body["created"]
    assert [a["startsAt"] for a in created] == [iso(date(2026, 11, d), "09:00") for d in (2, 9, 16, 23)]
    assert {a["seriesId"] for a in created} == {body["seriesId"]}
    assert all(a["reason"] == "Rééducation genou" and a["durationMin"] == 45 and a["status"] == "scheduled" for a in created)
    assert 'daftar_appointments_created_total{source="series"} 4.0' in client.get("/metrics").text


def test_a_conflict_refuses_the_whole_series(
    client: TestClient, kine: Any, amira: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory, db: Any
) -> None:
    taken = make_appointment(make_patient(kine), practitioner_id=kine.practitioners[0].id, starts_at=at(date(2026, 11, 16), "09:00"))
    res = client.post("/api/appointments/series", json=series_body(kine, amira), headers=as_user(kine, "assistant"))
    body = assert_problem(res, 409, "appointment_conflict")
    assert [c["id"] for c in body["conflicts"]] == [taken.id]
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 1


def test_skip_conflicts_and_closed_days(
    client: TestClient, kine: Any, amira: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    owner = as_user(kine, "owner")
    make_appointment(make_patient(kine), practitioner_id=kine.practitioners[0].id, starts_at=at(date(2026, 11, 9), "09:15"))
    client.post("/api/closures", json={"startsOn": "2026-11-23"}, headers=owner)
    res = client.post("/api/appointments/series", json=series_body(kine, amira, skipConflicts=True), headers=owner)
    assert res.status_code == 201, res.text
    body = res.json()
    assert [a["startsAt"][:10] for a in body["created"]] == ["2026-11-02", "2026-11-16"]
    assert body["skipped"] == [{"startsAt": iso(date(2026, 11, 9), "09:00"), "reason": "conflict"},
                               {"startsAt": iso(date(2026, 11, 23), "09:00"), "reason": "closed"}]


def test_closed_days_are_skipped_even_without_skip_conflicts(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    owner = as_user(kine, "owner")
    client.post("/api/closures", json={"startsOn": "2026-11-09"}, headers=owner)
    body = client.post("/api/appointments/series", json=series_body(kine, amira), headers=owner).json()
    assert len(body["created"]) == 3 and body["skipped"] == [{"startsAt": iso(date(2026, 11, 9), "09:00"), "reason": "closed"}]


def test_fifty_two_sessions(client: TestClient, kine: Any, amira: Any, as_user: Factory) -> None:
    body = series_body(kine, amira, durationMin=30, rule={"weekdays": [1], "count": 52})
    res = client.post("/api/appointments/series", json=body, headers=as_user(kine, "assistant"))
    assert res.status_code == 201, res.text
    created = res.json()["created"]
    assert len(created) == 52
    assert created[-1]["startsAt"] == iso(date(2027, 10, 25), "09:00")  # a year of Mondays, always 09:00 in Tunis


def test_a_race_during_creation_is_skipped_or_refused(
    client: TestClient, kine: Any, amira: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory,
    monkeypatch: pytest.MonkeyPatch, db: Any,
) -> None:
    """The check sees nothing (another request books meanwhile); the database refuses that one occurrence."""
    make_appointment(make_patient(kine), practitioner_id=kine.practitioners[0].id, starts_at=at(date(2026, 11, 9), "09:00"))
    monkeypatch.setattr(scheduling, "find_conflicts", lambda *a, **k: [])
    h = as_user(kine, "assistant")
    assert_problem(client.post("/api/appointments/series", json=series_body(kine, amira), headers=h), 409, "appointment_conflict")
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 1
    res = client.post("/api/appointments/series", json=series_body(kine, amira, skipConflicts=True), headers=h)
    assert res.status_code == 201, res.text
    assert res.json()["skipped"] == [{"startsAt": iso(date(2026, 11, 9), "09:00"), "reason": "conflict"}]
    assert len(res.json()["created"]) == 3


@pytest.mark.parametrize(
    ("override", "status", "code"),
    [
        ({"rule": {"weekdays": [1], "count": 0}}, 422, "validation"),
        ({"rule": {"weekdays": [1], "count": 53}}, 422, "validation"),
        ({"rule": {"weekdays": [], "count": 3}}, 422, "validation"),
        ({"rule": {"weekdays": [8], "count": 3}}, 422, "validation"),
        ({"rule": {"weekdays": [0], "count": 3}}, 422, "validation"),
        ({"rule": None}, 422, "validation"),
        ({"startsAt": iso(FRI, "08:00")}, 422, "in_past"),
        ({"startsAt": "2026-11-02T09:00:30+01:00"}, 422, "invalid_time"),
        ({"patientId": 999999}, 404, "not_found"),
        ({"practitionerId": 999999}, 404, "not_found"),
        ({"serviceId": 999999}, 404, "not_found"),
        ({"rule": {"weekdays": [7], "count": 3}}, 422, "series_empty"),
    ],
)
def test_series_validation(client: TestClient, kine: Any, amira: Any, as_user: Factory, override: dict[str, Any], status: int, code: str) -> None:
    h = as_user(kine, "assistant")
    res = client.post("/api/appointments/series", json=series_body(kine, amira, **override), headers=h)
    assert_problem(res, status, code)
    if code != "series_empty":
        assert_problem(client.post("/api/appointments/series/preview", json=series_body(kine, amira, **override), headers=h), status, code)


def test_a_service_gives_the_duration(client: TestClient, kine: Any, amira: Any, make_service: Factory, as_user: Factory) -> None:
    seance = make_service(kine, "Séance", 45)
    body = series_body(kine, amira, serviceId=seance.id)
    del body["durationMin"]
    created = client.post("/api/appointments/series", json=body, headers=as_user(kine, "assistant")).json()["created"]
    assert {(a["durationMin"], a["serviceName"]) for a in created} == {(45, "Séance")}


def test_cancel_the_rest_of_a_series(client: TestClient, kine: Any, amira: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(kine, "assistant")
    made = client.post("/api/appointments/series", json=series_body(kine, amira), headers=h).json()
    url = f"/api/appointments/series/{made['seriesId']}/cancel"
    res = client.post(url, json={"from": "2026-11-09"}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json() == {"cancelled": 3}
    statuses = [a["status"] for a in client.get("/api/appointments?from=2026-11-01&to=2026-11-30", headers=h).json()]
    assert statuses == ["scheduled", "cancelled", "cancelled", "cancelled"]
    assert client.post(url, json={"from": "2026-11-09"}, headers=h).json() == {"cancelled": 0}
    clock.set(at(MON, "10:00"))
    client.post(f"/api/appointments/{made['created'][0]['id']}/status", json={"status": "done"}, headers=h)
    assert client.post(url, json={}, headers=h).json() == {"cancelled": 0}  # from today on: the done one stays


def test_cancel_unknown_or_foreign_series_is_404(client: TestClient, kine: Any, amira: Any, make_practice: Factory, as_user: Factory) -> None:
    made = client.post("/api/appointments/series", json=series_body(kine, amira), headers=as_user(kine, "assistant")).json()
    stranger = as_user(make_practice(), "owner")
    assert_problem(client.post(f"/api/appointments/series/{made['seriesId']}/cancel", json={}, headers=stranger), 404, "not_found")
    assert_problem(client.post("/api/appointments/series/00000000-0000-0000-0000-000000000000/cancel", json={}, headers=stranger), 404, "not_found")
    assert_problem(client.post("/api/appointments/series/pas-un-uuid/cancel", json={}, headers=stranger), 404, "not_found")


def test_series_need_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, make_patient: Factory, as_user: Factory) -> None:
    for url in ("/api/appointments/series/preview", "/api/appointments/series",
                "/api/appointments/series/00000000-0000-0000-0000-000000000000/cancel"):
        assert_problem(client.post(url, json={}), 401, "unauthorized")
    p = make_practice(status="suspended", practitioners=1)
    pat = make_patient(p)
    h = as_user(p, "assistant")
    body = {"patientId": pat.id, "startsAt": iso(MON, "09:00"), "rule": {"weekdays": [1], "count": 2}}
    assert client.post("/api/appointments/series/preview", json=body, headers=h).status_code == 200  # only reads
    assert_problem(client.post("/api/appointments/series", json=body, headers=h), 402, "subscription_suspended")
    assert_problem(client.post("/api/appointments/series/00000000-0000-0000-0000-000000000000/cancel", json={}, headers=h),
                   402, "subscription_suspended")
