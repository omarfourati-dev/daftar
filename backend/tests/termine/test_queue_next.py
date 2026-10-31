"""“Patient suivant” (section 16.2): who is next, late appointment patients, calling the next one race-free."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from daftar import queue as queue_module
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, SAT, Factory, at

NEXT = "/api/queue/next"
CALL = "/api/queue/call-next"


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet du Lac", practitioners=["Dr. A", "Dr. B"])


@pytest.fixture
def staff(lac: Any, as_user: Factory) -> dict[str, str]:
    return as_user(lac, "assistant")


def walk_in(client: TestClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    res = client.post("/api/queue", json={"name": name}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def arrive(client: TestClient, headers: dict[str, str], appt: Any) -> None:
    res = client.post(f"/api/appointments/{appt.id}/status", json={"status": "arrived"}, headers=headers)
    assert res.status_code == 200, res.text


def nxt(client: TestClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    res = client.get(NEXT, params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def tickets(entries: list[dict[str, Any]]) -> list[int]:
    return [e["ticketNo"] for e in entries]


def test_the_due_appointment_patient_goes_first(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory
) -> None:
    walk_in(client, staff, "Passant")
    amira = make_patient(lac, first_name="Amira")
    appt = make_appointment(amira, practitioner_id=lac.practitioners[0].id, starts_at=at(FRI, "09:00"))
    arrive(client, staff, appt)
    body = nxt(client, staff)
    assert (body["entry"]["ticketNo"], body["entry"]["appointmentId"], body["reason"]) == (2, appt.id, "appointment")
    assert tickets(body["upcoming"]) == [1] and body["lateAppointments"] == []


@pytest.mark.parametrize(("start", "first", "reason"), [("09:05", 2, "appointment"), ("09:06", 1, "waiting_list")])
def test_an_appointment_is_due_five_minutes_before_its_start(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory,
    start: str, first: int, reason: str,
) -> None:
    walk_in(client, staff, "Passant")
    appt = make_appointment(make_patient(lac), starts_at=at(FRI, start))
    arrive(client, staff, appt)  # came early: counts like everybody else until the appointment is due
    body = nxt(client, staff)
    assert (body["entry"]["ticketNo"], body["reason"]) == (first, reason)


def test_an_absent_appointment_patient_gives_way(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory
) -> None:
    make_appointment(make_patient(lac), starts_at=at(FRI, "09:00"))  # not there
    walk_in(client, staff, "Premier")
    walk_in(client, staff, "Second")
    body = nxt(client, staff)
    assert (body["entry"]["name"], body["reason"], tickets(body["upcoming"])) == ("Premier", "waiting_list", [2])


def test_a_ticket_taken_without_marking_the_arrival_counts(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory
) -> None:
    walk_in(client, staff, "Passant")
    amira = make_patient(lac)
    make_appointment(amira, starts_at=at(FRI, "08:55"))
    client.post("/api/queue", json={"patientId": amira.id}, headers=staff)
    body = nxt(client, staff)
    assert (body["entry"]["patientId"], body["reason"]) == (amira.id, "appointment")


def test_several_due_appointments_go_by_their_time_then_the_rest_by_ticket(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory
) -> None:
    a = lac.practitioners[0].id
    walk_in(client, staff, "W1")  # ticket 1
    nine = make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(FRI, "09:00"))
    half_past_eight = make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(FRI, "08:30"))
    arrive(client, staff, nine)  # ticket 2
    arrive(client, staff, half_past_eight)  # ticket 3
    walk_in(client, staff, "W4")  # ticket 4
    body = nxt(client, staff)
    assert body["entry"]["ticketNo"] == 3 and tickets(body["upcoming"]) == [2, 1, 4]


def test_called_or_treated_people_are_not_next(client: TestClient, lac: Any, staff: dict[str, str]) -> None:
    first, second, third = (walk_in(client, staff, n) for n in ("A", "B", "C"))
    client.post(f"/api/queue/{first['id']}/status", json={"status": "called"}, headers=staff)
    client.post(f"/api/queue/{second['id']}/status", json={"status": "in_treatment"}, headers=staff)
    body = nxt(client, staff)
    assert body["entry"]["id"] == third["id"] and body["upcoming"] == []


def test_nobody_waiting(client: TestClient, lac: Any, staff: dict[str, str]) -> None:
    assert nxt(client, staff) == {"entry": None, "reason": None, "lateAppointments": [], "upcoming": []}


def test_late_appointment_patients(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory, clock: Any
) -> None:
    a, b = (d.id for d in lac.practitioners)

    def appt(hhmm: str, doctor: int, **v: Any) -> Any:
        return make_appointment(make_patient(lac), practitioner_id=doctor, starts_at=at(FRI, hhmm), duration_min=5, **v)

    late_a = appt("08:40", a, status="confirmed")
    late_b = appt("08:50", b)
    appt("08:51", a)  # 9 minutes: not late yet
    appt("08:30", a, status="arrived")
    appt("08:20", a, status="cancelled")
    with_ticket = appt("08:45", b)
    client.post("/api/queue", json={"patientId": with_ticket.patient_id}, headers=staff)  # there: the ticket is the arrival (M4)
    make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(FRI, "08:40") - timedelta(days=1))
    assert [x["id"] for x in nxt(client, staff)["lateAppointments"]] == [late_a.id, late_b.id]
    assert [x["id"] for x in nxt(client, staff, practitionerId=a)["lateAppointments"]] == [late_a.id]
    late = nxt(client, staff, practitionerId=b)["lateAppointments"]
    assert [x["id"] for x in late] == [late_b.id] and late[0]["status"] == "scheduled"  # marked, not set to no-show
    clock.advance(minutes=1)
    assert len(nxt(client, staff)["lateAppointments"]) == 3


def test_each_practitioner_sees_their_patients_and_the_walk_ins(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory
) -> None:
    a, b = (d.id for d in lac.practitioners)
    walk_in(client, staff, "Passant")  # ticket 1
    amira = make_appointment(make_patient(lac, first_name="Amira"), practitioner_id=b, starts_at=at(FRI, "09:00"))
    karim = make_appointment(make_patient(lac, first_name="Karim"), practitioner_id=a, starts_at=at(FRI, "09:00"))
    arrive(client, staff, amira)  # ticket 2
    arrive(client, staff, karim)  # ticket 3
    for_a = nxt(client, staff, practitionerId=a)
    assert (for_a["entry"]["ticketNo"], tickets(for_a["upcoming"])) == (3, [1])
    for_b = nxt(client, staff, practitionerId=b)
    assert (for_b["entry"]["ticketNo"], tickets(for_b["upcoming"])) == (2, [1])
    everyone = nxt(client, staff)
    assert everyone["entry"]["ticketNo"] == 2 and tickets(everyone["upcoming"]) == [3, 1]


def test_call_the_next_one(client: TestClient, lac: Any, staff: dict[str, str], clock: Any) -> None:
    walk_in(client, staff, "Premier")
    walk_in(client, staff, "Second")
    clock.advance(minutes=3)
    res = client.post(CALL, json={}, headers=staff)
    assert res.status_code == 200, res.text
    called = res.json()
    assert (called["ticketNo"], called["status"], called["calledAt"]) == (1, "called", "2026-10-30T09:03:00+01:00")
    assert nxt(client, staff)["entry"]["ticketNo"] == 2
    assert client.get(f"/api/public/display/{lac.display_token}").json()["called"] == [1]
    assert client.post(CALL, headers=staff).json()["ticketNo"] == 2  # the body is optional
    assert_problem(client.post(CALL, json={}, headers=staff), 409, "queue_empty")


def test_call_the_next_one_of_a_practitioner(
    client: TestClient, lac: Any, staff: dict[str, str], make_patient: Factory, make_appointment: Factory, db: Any
) -> None:
    a, b = (d.id for d in lac.practitioners)
    walk_in(client, staff, "Passant")
    karim = make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(FRI, "09:00"))
    arrive(client, staff, karim)
    assert client.post(CALL, json={"practitionerId": b}, headers=staff).json()["ticketNo"] == 1
    called = client.post(CALL, json={"practitionerId": a}, headers=staff).json()
    assert called["appointmentId"] == karim.id
    appt = client.get(f"/api/appointments/{karim.id}", headers=staff).json()
    assert appt["status"] == "arrived"  # called is not yet in treatment


@pytest.mark.parametrize(("waiting", "expected"), [(2, [200, 200]), (1, [200, 409])])
def test_two_calls_at_once_never_call_the_same_person(
    app: Any, lac: Any, staff: dict[str, str], monkeypatch: pytest.MonkeyPatch, waiting: int, expected: list[int]
) -> None:
    with TestClient(app) as c:
        for n in range(waiting):
            walk_in(c, staff, f"P{n}")
    original = queue_module.next_in_line

    def slow(*args: Any, **kwargs: Any) -> Any:
        found = original(*args, **kwargs)
        threading.Event().wait(0.3)  # widen the window between choosing and calling
        return found

    monkeypatch.setattr(queue_module, "next_in_line", slow)
    results: list[Any] = []

    def call() -> None:
        with TestClient(app) as c:
            results.append(c.post(CALL, json={}, headers=staff))

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.status_code for r in results) == expected, [r.text for r in results]
    called = [r.json()["ticketNo"] for r in results if r.status_code == 200]
    assert len(called) == len(set(called))


def test_only_today_counts(client: TestClient, lac: Any, staff: dict[str, str], clock: Any) -> None:
    clock.set(at(FRI, "17:00"))
    walk_in(client, staff, "Hier soir")
    clock.set(at(SAT, "00:10"))  # Friday 23:10 UTC – already Saturday in Tunis
    assert nxt(client, staff)["entry"] is None
    assert_problem(client.post(CALL, json={}, headers=staff), 409, "queue_empty")


def test_other_practices_are_invisible(
    client: TestClient, lac: Any, staff: dict[str, str], make_practice: Factory, make_queue_entry: Factory, as_user: Factory
) -> None:
    other = make_practice(practitioners=1)
    make_queue_entry(other, 1, name="Ailleurs")
    assert nxt(client, staff)["entry"] is None
    assert_problem(client.post(CALL, json={}, headers=staff), 409, "queue_empty")
    foreign = other.practitioners[0].id
    assert_problem(client.get(NEXT, params={"practitionerId": foreign}, headers=staff), 404, "not_found")
    assert_problem(client.post(CALL, json={"practitionerId": foreign}, headers=staff), 404, "not_found")


def test_needs_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, make_queue_entry: Factory, as_user: Factory) -> None:
    assert_problem(client.get(NEXT), 401, "unauthorized")
    assert_problem(client.post(CALL, json={}), 401, "unauthorized")
    assert_problem(client.get(NEXT, headers=as_user(role="admin")), 403, "forbidden")
    p = make_practice(status="suspended")
    make_queue_entry(p, 1, name="X")
    h = as_user(p, "dentist")
    assert nxt(client, h)["entry"]["ticketNo"] == 1  # reading goes on
    assert_problem(client.post(CALL, json={}, headers=h), 402, "subscription_suspended")
