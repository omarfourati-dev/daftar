"""``GET /api/availability`` (section 11.1): free starts on the practice's grid, per practitioner."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, SAT, SUN, Factory, at


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet du Lac", practitioners=["Dr. A", "Dr. B"])


def slots(client: TestClient, headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:
    res = client.get("/api/availability", params=params, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["date"] == params["date"]
    return body["slots"]


def times(items: list[dict[str, Any]]) -> list[str]:
    return [s["time"] for s in items]


def test_a_free_monday(client: TestClient, lac: Any, as_user: Factory) -> None:
    a, b = (d.id for d in lac.practitioners)
    got = slots(client, as_user(lac, "assistant"), date=MON.isoformat(), durationMin=30)
    morning = [f"{h:02d}:{m:02d}" for h in range(8, 12) for m in (0, 15, 30, 45)] + ["12:00"]
    afternoon = [f"{h:02d}:{m:02d}" for h in range(14, 18) for m in (0, 15, 30, 45)][:-1]
    assert times(got) == morning + afternoon  # 12:00–12:30 is the last before the lunch break, 17:30 the last start
    assert all(s["practitionerIds"] == [a, b] for s in got)


def test_default_duration_and_the_lunch_break(client: TestClient, lac: Any, as_user: Factory) -> None:
    h = as_user(lac, "assistant")
    assert "12:00" in times(slots(client, h, date=MON.isoformat()))  # practice default: 30 min
    long = times(slots(client, h, date=MON.isoformat(), durationMin=45))
    assert long[-1] == "17:15" and "11:45" in long and "12:00" not in long and "12:15" not in long


def test_booked_times_are_gone_for_that_practitioner(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    a, b = (d.id for d in lac.practitioners)
    make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(MON, "09:00"), duration_min=30)
    make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(MON, "10:00"), duration_min=30, status="cancelled")
    make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(MON, "11:00"), duration_min=30, status="no_show")
    make_appointment(make_patient(lac), practitioner_id=b, starts_at=at(MON, "14:00"), duration_min=60, status="requested")
    got = {s["time"]: s["practitionerIds"] for s in slots(client, as_user(lac, "assistant"), date=MON.isoformat(), durationMin=30)}
    assert got["08:30"] == [a, b]
    assert got["08:45"] == got["09:00"] == got["09:15"] == [b]
    assert got["09:30"] == [a, b]
    assert got["10:00"] == got["11:00"] == [a, b]  # cancelled and no-show free their slot
    assert got["14:00"] == got["14:45"] == [a] and got["15:00"] == [a, b]  # an online request blocks
    only_b = slots(client, as_user(lac, "assistant"), date=MON.isoformat(), durationMin=30, practitionerId=b)
    assert "09:00" in times(only_b) and "14:30" not in times(only_b)
    assert all(s["practitionerIds"] == [b] for s in only_b)


def test_closed_days(client: TestClient, lac: Any, as_user: Factory) -> None:
    owner = as_user(lac, "owner")
    assert slots(client, owner, date=SUN.isoformat()) == []  # no opening hours on Sunday
    client.post("/api/closures", json={"startsOn": MON.isoformat(), "label": "Aïd"}, headers=owner)
    assert slots(client, owner, date=MON.isoformat()) == []


def test_no_slots_in_the_past(client: TestClient, lac: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    clock.set(at(FRI, "10:05"))
    today = times(slots(client, h, date=FRI.isoformat()))
    assert today[0] == "10:15" and "10:00" not in today
    assert slots(client, h, date="2026-10-29") == []


def test_today_follows_tunis_time_around_midnight(client: TestClient, lac: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    clock.set(at(SAT, "00:10"))  # still Friday 23:10 in UTC
    assert slots(client, h, date=FRI.isoformat()) == []
    assert times(slots(client, h, date=SAT.isoformat()))[0] == "08:00"


def test_inactive_practitioners_are_not_offered(client: TestClient, make_practice: Factory, make_practitioner: Factory, as_user: Factory) -> None:
    p = make_practice()
    active = make_practitioner(p, "Dr. Actif")
    make_practitioner(p, "Dr. Parti", active=False)
    assert slots(client, as_user(p, "assistant"), date=MON.isoformat())[0]["practitionerIds"] == [active.id]


def test_a_practice_without_practitioners_has_one_calendar(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice()
    make_appointment(make_patient(p), starts_at=at(MON, "09:00"), duration_min=30)
    got = {s["time"]: s["practitionerIds"] for s in slots(client, as_user(p, "assistant"), date=MON.isoformat())}
    assert got["08:30"] == [] and "09:00" not in got and "09:15" not in got and got["09:30"] == []


def test_other_practices_do_not_block(
    client: TestClient, lac: Any, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    other = make_practice()
    make_appointment(make_patient(other), starts_at=at(MON, "09:00"))
    assert slots(client, as_user(lac, "assistant"), date=MON.isoformat())[4]["time"] == "09:00"


def test_grid_follows_the_slot_length(client: TestClient, make_practice: Factory, as_user: Factory) -> None:
    p = make_practice(slot_minutes=20, weekly_hours={"1": [["08:10", "09:30"]]})
    assert times(slots(client, as_user(p, "assistant"), date=MON.isoformat(), durationMin=20)) == ["08:10", "08:30", "08:50", "09:10"]


@pytest.mark.parametrize(
    ("params", "code"),
    [({}, "validation"), ({"date": "02/11/2026"}, "validation"), ({"date": "2026-11-02", "durationMin": 4}, "validation"),
     ({"date": "2026-11-02", "durationMin": 481}, "validation"), ({"date": "2026-11-02", "practitionerId": "x"}, "validation")],
)
def test_availability_validation(client: TestClient, lac: Any, as_user: Factory, params: dict[str, Any], code: str) -> None:
    assert_problem(client.get("/api/availability", params=params, headers=as_user(lac, "assistant")), 422, code)


def test_availability_needs_a_token_and_own_practitioners(client: TestClient, lac: Any, make_practice: Factory, as_user: Factory) -> None:
    assert_problem(client.get(f"/api/availability?date={MON}"), 401, "unauthorized")
    assert_problem(client.get(f"/api/availability?date={MON}", headers=as_user(role="admin")), 403, "forbidden")
    foreign = make_practice(practitioners=1).practitioners[0].id
    res = client.get(f"/api/availability?date={MON}&practitionerId={foreign}", headers=as_user(lac, "owner"))
    assert_problem(res, 404, "not_found")
