"""``GET /api/availability/next`` (section 16.1): the next free starts over several days for the phone booking."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, SAT, Factory, at, iso

URL = "/api/availability/next"


def nexts(client: TestClient, headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:
    res = client.get(URL, params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture
def short(make_practice: Factory) -> Any:
    """Open Friday 09:00–10:00 and Monday 08:00–09:00 only, one practitioner."""
    return make_practice(weekly_hours={"5": [["09:00", "10:00"]], "1": [["08:00", "09:00"]]}, practitioners=["Dr. A"])


def test_next_free_times_over_several_days(
    client: TestClient, short: Any, make_patient: Factory, make_appointment: Factory, make_service: Factory, as_user: Factory
) -> None:
    a = short.practitioners[0].id
    make_appointment(make_patient(short), practitioner_id=a, starts_at=at(FRI, "09:00"), duration_min=30)
    consult = make_service(short, "Consultation", 30)
    got = nexts(client, as_user(short, "assistant"), serviceId=consult.id, limit=3)
    assert got == [{"startsAt": iso(FRI, "09:30"), "practitionerId": a},
                   {"startsAt": iso(MON, "08:00"), "practitionerId": a},
                   {"startsAt": iso(MON, "08:15"), "practitionerId": a}]


def test_default_limit_and_duration(client: TestClient, make_practice: Factory, as_user: Factory, clock: Any) -> None:
    p = make_practice(practitioners=1)
    clock.set(at(FRI, "17:00"))
    got = nexts(client, as_user(p, "assistant"))
    assert len(got) == 8  # default limit
    assert [g["startsAt"] for g in got[:3]] == [iso(FRI, "17:00"), iso(FRI, "17:15"), iso(FRI, "17:30")]
    assert got[3]["startsAt"] == iso(SAT, "08:00")  # 30 min default: 17:45 does not fit before 18:00
    long = nexts(client, as_user(p, "assistant"), durationMin=60, limit=2)
    assert [g["startsAt"] for g in long] == [iso(FRI, "17:00"), iso(SAT, "08:00")]


def test_the_first_free_practitioner_is_proposed(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice(practitioners=["Dr. A", "Dr. B"])
    a, b = (d.id for d in p.practitioners)
    make_appointment(make_patient(p), practitioner_id=a, starts_at=at(FRI, "09:00"), duration_min=30)
    got = nexts(client, as_user(p, "assistant"), limit=3)
    assert got == [{"startsAt": iso(FRI, "09:00"), "practitionerId": b},
                   {"startsAt": iso(FRI, "09:15"), "practitionerId": b},
                   {"startsAt": iso(FRI, "09:30"), "practitionerId": a}]
    only_a = nexts(client, as_user(p, "assistant"), practitionerId=a, limit=1)
    assert only_a == [{"startsAt": iso(FRI, "09:30"), "practitionerId": a}]


def test_the_patient_must_be_free_too(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice(practitioners=["Dr. A", "Dr. B"])
    amira = make_patient(p)
    make_appointment(amira, practitioner_id=p.practitioners[0].id, starts_at=at(FRI, "09:00"), duration_min=60)
    got = nexts(client, as_user(p, "assistant"), patientId=amira.id, limit=1)
    assert got == [{"startsAt": iso(FRI, "10:00"), "practitionerId": p.practitioners[0].id}]


def test_without_practitioners_the_one_calendar(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    got = nexts(client, as_user(make_practice(), "assistant"), limit=1)
    assert got == [{"startsAt": iso(FRI, "09:00"), "practitionerId": None}]


def test_at_most_fourteen_days_ahead(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice(weekly_hours={"1": [["09:00", "10:00"]]}, practitioners=1)  # Mondays only
    owner = as_user(p, "owner")
    assert nexts(client, owner, limit=1)[0]["startsAt"] == iso(MON, "09:00")
    client.post("/api/closures", json={"startsOn": "2026-11-02", "endsOn": "2026-11-09"}, headers=owner)
    assert nexts(client, owner) == []  # 16.11 is 17 days away
    p2 = make_practice(weekly_hours={"5": [["09:00", "10:00"]]}, practitioners=1)  # Fridays only
    owner2 = as_user(p2, "owner")
    client.post("/api/closures", json={"startsOn": "2026-10-30", "endsOn": "2026-11-06"}, headers=owner2)
    assert nexts(client, owner2, limit=1) == [{"startsAt": iso(date(2026, 11, 13), "09:00"),
                                               "practitionerId": p2.practitioners[0].id}]  # 14th day still counts


def test_tunis_today_around_midnight(client: TestClient, make_practice: Factory, as_user: Factory, clock: Any) -> None:
    p = make_practice(practitioners=1)
    clock.set(at(SAT, "00:10"))  # Friday 23:10 UTC
    assert nexts(client, as_user(p, "assistant"), limit=1)[0]["startsAt"] == iso(SAT, "08:00")


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 51}, {"durationMin": 4}, {"serviceId": "x"}])
def test_validation(client: TestClient, make_practice: Factory, as_user: Factory, params: dict[str, Any]) -> None:
    assert_problem(client.get(URL, params=params, headers=as_user(make_practice(), "assistant")), 422, "validation")


def test_inactive_service(client: TestClient, make_practice: Factory, make_service: Factory, as_user: Factory) -> None:
    p = make_practice()
    old = make_service(p, active=False)
    assert_problem(client.get(URL, params={"serviceId": old.id}, headers=as_user(p, "assistant")), 422, "service_inactive")


def test_foreign_ids_are_404(
    client: TestClient, make_practice: Factory, make_service: Factory, make_patient: Factory, as_user: Factory
) -> None:
    other = make_practice(practitioners=1)
    h = as_user(make_practice(), "assistant")
    for params in ({"serviceId": make_service(other).id}, {"practitionerId": other.practitioners[0].id},
                   {"patientId": make_patient(other).id}):
        assert_problem(client.get(URL, params=params, headers=h), 404, "not_found")


def test_needs_a_token_and_a_practice(client: TestClient, as_user: Factory) -> None:
    assert_problem(client.get(URL), 401, "unauthorized")
    assert_problem(client.get(URL, headers=as_user(role="admin")), 403, "forbidden")
