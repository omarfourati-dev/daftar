"""Status workflow (backlog B3, section 5): requested → confirmed → arrived → in_treatment → done / no_show / cancelled,
with the waiting-room side effects of ``arrived``, ``in_treatment`` and ``done``."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar.tables import queue_entry
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, Factory, at, iso


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet du Lac", practitioners=["Dr. A"])


@pytest.fixture
def amira(lac: Any, make_patient: Factory) -> Any:
    return make_patient(lac, first_name="Amira", last_name="Ben Ali", phone="+21620111222")


def status(client: TestClient, headers: dict[str, str], appt_id: int, value: str) -> Any:
    return client.post(f"/api/appointments/{appt_id}/status", json={"status": value}, headers=headers)


def queue_rows(db: Any) -> list[Any]:
    with db.connect() as conn:
        return list(conn.execute(select(queue_entry).order_by(queue_entry.c.ticket_no)).all())


def test_the_happy_path_with_the_waiting_room(
    client: TestClient, lac: Any, amira: Any, make_appointment: Factory, make_queue_entry: Factory, as_user: Factory, db: Any, clock: Any
) -> None:
    make_queue_entry(lac, 1, name="Déjà là")
    appt = make_appointment(amira, starts_at=at(FRI, "09:30"), practitioner_id=lac.practitioners[0].id)
    h = as_user(lac, "assistant")
    assert status(client, h, appt.id, "confirmed").json()["status"] == "confirmed"
    clock.advance(minutes=20)
    res = status(client, h, appt.id, "arrived")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "arrived"
    entry = queue_rows(db)[1]
    assert (entry.ticket_no, entry.name, entry.phone, entry.patient_id, entry.appointment_id, entry.status, entry.day) == (
        2, "Amira Ben Ali", "+21620111222", amira.id, appt.id, "waiting", FRI)
    assert status(client, h, appt.id, "arrived").status_code == 200  # twice: still one ticket
    assert len(queue_rows(db)) == 2
    clock.advance(minutes=15)
    status(client, h, appt.id, "in_treatment")
    entry = queue_rows(db)[1]
    assert entry.status == "in_treatment" and entry.called_at == clock.now()
    clock.advance(minutes=30)
    assert status(client, h, appt.id, "done").json()["status"] == "done"
    entry = queue_rows(db)[1]
    assert entry.status == "done" and entry.done_at == clock.now()
    queue = client.get("/api/queue", headers=h).json()
    assert [(e["ticketNo"], e["appointmentId"]) for e in queue] == [(1, None), (2, appt.id)]


def test_online_requests_are_confirmed_or_declined(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory) -> None:
    h = as_user(lac, "assistant")
    yes = make_appointment(amira, starts_at=at(MON, "09:00"), status="requested", source="online")
    no = make_appointment(amira, starts_at=at(MON, "10:00"), status="requested", source="online")
    assert status(client, h, yes.id, "confirmed").json()["status"] == "confirmed"
    assert status(client, h, no.id, "cancelled").json()["status"] == "cancelled"


@pytest.mark.parametrize(
    ("start", "target"),
    [("requested", "arrived"), ("requested", "done"), ("requested", "no_show"), ("in_treatment", "cancelled"),
     ("in_treatment", "no_show"), ("in_treatment", "scheduled"), ("done", "cancelled"), ("done", "no_show"),
     ("done", "scheduled"), ("cancelled", "done"), ("cancelled", "arrived"), ("no_show", "done"), ("scheduled", "requested")],
)
def test_impossible_transitions(
    client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, start: str, target: str
) -> None:
    appt = make_appointment(amira, starts_at=at(FRI, "08:30"), status=start)
    assert_problem(status(client, as_user(lac, "assistant"), appt.id, target), 409, "invalid_transition")


@pytest.mark.parametrize(
    ("start", "target"),
    [("scheduled", "confirmed"), ("confirmed", "scheduled"), ("scheduled", "no_show"), ("confirmed", "cancelled"),
     ("arrived", "confirmed"), ("in_treatment", "arrived"), ("done", "in_treatment"), ("no_show", "scheduled"),
     ("no_show", "arrived"), ("cancelled", "confirmed"), ("scheduled", "done"), ("scheduled", "in_treatment")],
)
def test_possible_transitions(
    client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, start: str, target: str
) -> None:
    appt = make_appointment(amira, starts_at=at(FRI, "08:30"), status=start)
    res = status(client, as_user(lac, "assistant"), appt.id, target)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == target


def test_arrival_and_treatment_only_on_the_day(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory) -> None:
    h = as_user(lac, "assistant")
    tomorrow = make_appointment(amira, starts_at=at(MON, "09:00"))
    yesterday = make_appointment(amira, starts_at=at(FRI, "09:00") - timedelta(days=1))
    for appt in (tomorrow, yesterday):
        assert_problem(status(client, h, appt.id, "arrived"), 409, "not_today")
        assert_problem(status(client, h, appt.id, "in_treatment"), 409, "not_today")
    assert_problem(status(client, h, tomorrow.id, "done"), 409, "not_today")
    assert status(client, h, yesterday.id, "done").status_code == 200  # forgot to close it yesterday


def test_no_show_only_after_the_start(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    later = make_appointment(amira, starts_at=at(FRI, "09:30"))
    assert_problem(status(client, h, later.id, "no_show"), 409, "not_started")
    clock.set(at(FRI, "09:30"))
    assert status(client, h, later.id, "no_show").status_code == 200
    early = make_appointment(amira, starts_at=at(FRI, "11:00"))
    assert status(client, h, early.id, "done").status_code == 200  # came early, treated before the time


def test_cancelling_frees_the_slot_and_restoring_needs_it_free(
    client: TestClient, lac: Any, amira: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    h = as_user(lac, "assistant")
    doc = lac.practitioners[0].id
    appt = make_appointment(amira, starts_at=at(MON, "09:00"), practitioner_id=doc)
    status(client, h, appt.id, "cancelled")
    karim = make_patient(lac, first_name="Karim", last_name="T")
    taken = client.post("/api/appointments", json={"patientId": karim.id, "startsAt": iso(MON, "09:00"), "practitionerId": doc}, headers=h)
    assert taken.status_code == 201, taken.text
    body = assert_problem(status(client, h, appt.id, "scheduled"), 409, "appointment_conflict")
    assert [c["patientName"] for c in body["conflicts"]] == ["Karim T"]


def test_undoing_an_arrival_removes_the_waiting_ticket(
    client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, db: Any
) -> None:
    h = as_user(lac, "assistant")
    appt = make_appointment(amira, starts_at=at(FRI, "09:30"))
    status(client, h, appt.id, "arrived")
    assert len(queue_rows(db)) == 1
    status(client, h, appt.id, "confirmed")
    assert queue_rows(db) == []


def test_leaving_after_arrival(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, db: Any, clock: Any) -> None:
    h = as_user(lac, "assistant")
    appt = make_appointment(amira, starts_at=at(FRI, "09:00"))
    status(client, h, appt.id, "arrived")
    status(client, h, appt.id, "no_show")  # waited, then went away
    assert queue_rows(db)[0].status == "left"
    status(client, h, appt.id, "arrived")  # came back
    assert [(e.status, e.ticket_no) for e in queue_rows(db)] == [("waiting", 1)]


def test_treatment_without_arrival_needs_no_ticket(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, db: Any) -> None:
    appt = make_appointment(amira, starts_at=at(FRI, "09:00"))
    h = as_user(lac, "dentist")
    status(client, h, appt.id, "in_treatment")
    status(client, h, appt.id, "done")
    assert queue_rows(db) == []


def test_status_validation(client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory) -> None:
    appt = make_appointment(amira, starts_at=at(MON, "09:00"))
    assert_problem(status(client, as_user(lac, "assistant"), appt.id, "asleep"), 422, "validation")
    assert_problem(client.post(f"/api/appointments/{appt.id}/status", json={}, headers=as_user(lac, "assistant")), 422, "validation")


def test_arrival_links_the_patients_open_ticket(
    client: TestClient, lac: Any, amira: Any, make_appointment: Factory, as_user: Factory, db: Any
) -> None:
    h = as_user(lac, "assistant")
    ticket = client.post("/api/queue", json={"patientId": amira.id}, headers=h).json()  # took a ticket at the door
    appt = make_appointment(amira, starts_at=at(FRI, "09:30"))
    status(client, h, appt.id, "arrived")
    assert [(r.id, r.appointment_id, r.ticket_no) for r in queue_rows(db)] == [(ticket["id"], appt.id, 1)]
