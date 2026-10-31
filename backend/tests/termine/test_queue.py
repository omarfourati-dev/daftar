"""Waiting room (backlog D1, section 5): ``/api/queue…``, the public screen and the patient's ticket page."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from daftar import queue as queue_module
from daftar.tables import appointment, queue_entry
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, SAT, Factory, at


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet du Lac", phone="+21671000111", default_duration_min=20)


def test_take_a_ticket_for_a_patient(client: TestClient, lac: Any, make_patient: Factory, as_user: Factory) -> None:
    amira = make_patient(lac, first_name="Amira", last_name="Ben Ali", phone="+21620111222", alerts="Allergie pénicilline")
    res = client.post("/api/queue", json={"patientId": amira.id}, headers=as_user(lac, "assistant"))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {
        "id": body["id"], "ticketNo": 1, "name": "Amira Ben Ali", "phone": "+21620111222", "patientId": amira.id,
        "appointmentId": None, "appointmentAt": None, "status": "waiting", "arrivedAt": "2026-10-30T09:00:00+01:00",
        "calledAt": None, "doneAt": None, "ticketToken": body["ticketToken"], "position": 1, "peopleAhead": 0,
        "estimatedWaitMin": 0, "alerts": "Allergie pénicilline",
    }
    assert len(body["ticketToken"]) == 32


def test_take_a_ticket_with_only_a_name(client: TestClient, lac: Any, as_user: Factory) -> None:
    h = as_user(lac, "dentist")
    first = client.post("/api/queue", json={"name": "Monsieur sans dossier", "phone": "20 333 444"}, headers=h).json()
    second = client.post("/api/queue", json={"name": "Passant"}, headers=h).json()
    assert (first["ticketNo"], first["name"], first["phone"], first["patientId"], first["alerts"]) == (
        1, "Monsieur sans dossier", "+21620333444", None, "")
    assert (second["ticketNo"], second["phone"], second["position"], second["peopleAhead"], second["estimatedWaitMin"]) == (
        2, None, 2, 1, 20)


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [({}, 422, "name_required"), ({"name": "  "}, 422, "name_required"), ({"name": "x" * 121}, 422, "validation"),
     ({"name": "X", "phone": "123"}, 422, "invalid_phone"), ({"patientId": 999999}, 404, "not_found")],
)
def test_ticket_validation(client: TestClient, lac: Any, as_user: Factory, body: dict[str, Any], status: int, code: str) -> None:
    assert_problem(client.post("/api/queue", json=body, headers=as_user(lac, "assistant")), status, code)


def test_a_patient_gets_only_one_active_ticket_a_day(client: TestClient, lac: Any, make_patient: Factory, as_user: Factory) -> None:
    h = as_user(lac, "assistant")
    pat = make_patient(lac)
    first = client.post("/api/queue", json={"patientId": pat.id}, headers=h).json()
    assert_problem(client.post("/api/queue", json={"patientId": pat.id}, headers=h), 409, "already_in_queue")
    client.post(f"/api/queue/{first['id']}/status", json={"status": "done"}, headers=h)
    assert client.post("/api/queue", json={"patientId": pat.id}, headers=h).status_code == 201  # came back later


def test_queue_order_positions_and_waiting_time(client: TestClient, lac: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    ids = [client.post("/api/queue", json={"name": f"P{i}"}, headers=h).json()["id"] for i in range(1, 7)]
    client.post(f"/api/queue/{ids[0]}/status", json={"status": "done"}, headers=h)
    client.post(f"/api/queue/{ids[1]}/status", json={"status": "in_treatment"}, headers=h)
    client.post(f"/api/queue/{ids[3]}/status", json={"status": "called"}, headers=h)
    client.post(f"/api/queue/{ids[4]}/status", json={"status": "left"}, headers=h)
    items = client.get("/api/queue", headers=h).json()
    got = [(e["ticketNo"], e["status"], e["position"], e["peopleAhead"], e["estimatedWaitMin"]) for e in items]
    assert got == [
        (2, "in_treatment", None, 0, 0),
        (3, "waiting", 1, 1, 20),  # the called patient goes in first
        (4, "called", None, 0, 0),
        (6, "waiting", 2, 2, 40),
        (1, "done", None, 0, 0),
        (5, "left", None, 0, 0),
    ]


def test_status_changes_set_the_times(client: TestClient, lac: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    entry = client.post("/api/queue", json={"name": "P"}, headers=h).json()
    url = f"/api/queue/{entry['id']}/status"
    clock.advance(minutes=10)
    called = client.post(url, json={"status": "called"}, headers=h).json()
    assert called["calledAt"] == "2026-10-30T09:10:00+01:00" and called["doneAt"] is None
    clock.advance(minutes=2)
    recalled = client.post(url, json={"status": "called"}, headers=h).json()
    assert recalled["calledAt"] == "2026-10-30T09:12:00+01:00"  # calling again puts it on top of the screen
    clock.advance(minutes=1)
    treated = client.post(url, json={"status": "in_treatment"}, headers=h).json()
    assert treated["calledAt"] == "2026-10-30T09:12:00+01:00"
    clock.advance(minutes=20)
    done = client.post(url, json={"status": "done"}, headers=h).json()
    assert done["doneAt"] == "2026-10-30T09:33:00+01:00"
    back = client.post(url, json={"status": "waiting"}, headers=h).json()  # undo
    assert (back["calledAt"], back["doneAt"], back["position"]) == (None, None, 1)
    direct = client.post("/api/queue", json={"name": "Q"}, headers=h).json()
    treated = client.post(f"/api/queue/{direct['id']}/status", json={"status": "in_treatment"}, headers=h).json()
    assert treated["calledAt"] == "2026-10-30T09:33:00+01:00"  # treated without being called first
    assert_problem(client.post(url, json={"status": "gone"}, headers=h), 422, "validation")


def test_delete_a_ticket(client: TestClient, lac: Any, as_user: Factory) -> None:
    h = as_user(lac, "assistant")
    entry = client.post("/api/queue", json={"name": "P"}, headers=h).json()
    assert client.delete(f"/api/queue/{entry['id']}", headers=h).status_code == 204
    assert client.get("/api/queue", headers=h).json() == []
    assert_problem(client.delete(f"/api/queue/{entry['id']}", headers=h), 404, "not_found")


def test_ticket_numbers_start_again_each_day_in_tunis_time(client: TestClient, lac: Any, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    clock.set(at(FRI, "23:50"))
    assert client.post("/api/queue", json={"name": "Tard"}, headers=h).json()["ticketNo"] == 1
    assert client.post("/api/queue", json={"name": "Très tard"}, headers=h).json()["ticketNo"] == 2
    clock.set(at(SAT, "00:10"))  # 23:10 UTC on Friday, but Saturday in Tunis
    assert client.get("/api/queue", headers=h).json() == []
    assert client.post("/api/queue", json={"name": "Matinal"}, headers=h).json()["ticketNo"] == 1
    friday = client.get("/api/queue?day=2026-10-30", headers=h).json()
    assert [e["name"] for e in friday] == ["Tard", "Très tard"]
    assert_problem(client.get("/api/queue?day=30/10/2026", headers=h), 422, "validation")


def test_ticket_numbers_are_unique_under_parallel_requests(
    app: Any, lac: Any, as_user: Factory, monkeypatch: pytest.MonkeyPatch, db: Any
) -> None:
    original = queue_module.next_ticket_no

    def slow(conn: Any, practice_id: int, day: Any) -> int:
        number = original(conn, practice_id, day)
        threading.Event().wait(0.3)  # widen the window between reading and inserting
        return number

    monkeypatch.setattr(queue_module, "next_ticket_no", slow)
    h = as_user(lac, "assistant")
    results: list[Any] = []

    def take(n: int) -> None:
        with TestClient(app) as c:
            results.append(c.post("/api/queue", json={"name": f"P{n}"}, headers=h))

    threads = [threading.Thread(target=take, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.status_code for r in results) == [201] * 4, [r.text for r in results]
    with db.connect() as conn:
        assert sorted(conn.execute(select(queue_entry.c.ticket_no)).scalars()) == [1, 2, 3, 4]


def test_queue_entries_of_another_practice_are_404(client: TestClient, lac: Any, make_practice: Factory, make_patient: Factory, make_queue_entry: Factory, as_user: Factory) -> None:
    other = make_practice()
    foreign = make_queue_entry(other, 1, name="Ailleurs")
    h = as_user(lac, "assistant")
    assert client.get("/api/queue", headers=h).json() == []
    assert_problem(client.post(f"/api/queue/{foreign.id}/status", json={"status": "called"}, headers=h), 404, "not_found")
    assert_problem(client.delete(f"/api/queue/{foreign.id}", headers=h), 404, "not_found")
    assert_problem(client.post("/api/queue", json={"patientId": make_patient(other).id}, headers=h), 404, "not_found")


def test_queue_needs_a_token_and_an_active_subscription(client: TestClient, make_practice: Factory, make_queue_entry: Factory, as_user: Factory) -> None:
    assert_problem(client.get("/api/queue"), 401, "unauthorized")
    assert_problem(client.post("/api/queue", json={"name": "X"}), 401, "unauthorized")
    assert_problem(client.get("/api/queue", headers=as_user(role="admin")), 403, "forbidden")
    p = make_practice(status="suspended")
    entry = make_queue_entry(p, 1, name="X")
    h = as_user(p, "owner")
    assert client.get("/api/queue", headers=h).status_code == 200
    assert_problem(client.post("/api/queue", json={"name": "X"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.post(f"/api/queue/{entry.id}/status", json={"status": "called"}, headers=h), 402, "subscription_suspended")
    assert_problem(client.delete(f"/api/queue/{entry.id}", headers=h), 402, "subscription_suspended")


def test_a_linked_appointment_follows_the_queue(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, make_queue_entry: Factory, as_user: Factory, db: Any, clock: Any
) -> None:
    pat = make_patient(lac)
    appt = make_appointment(pat, starts_at=clock.now() + timedelta(minutes=30), status="arrived")
    entry = make_queue_entry(lac, 1, patient_id=pat.id, appointment_id=appt.id, name="X")
    h = as_user(lac, "assistant")

    def appt_status() -> str:
        with db.connect() as conn:
            return conn.execute(select(appointment.c.status).where(appointment.c.id == appt.id)).scalar_one()

    listed = client.get("/api/queue", headers=h).json()[0]
    assert (listed["appointmentId"], listed["appointmentAt"]) == (appt.id, "2026-10-30T09:30:00+01:00")
    client.post(f"/api/queue/{entry.id}/status", json={"status": "in_treatment"}, headers=h)
    assert appt_status() == "in_treatment"
    client.post(f"/api/queue/{entry.id}/status", json={"status": "done"}, headers=h)
    assert appt_status() == "done"
    client.post(f"/api/queue/{entry.id}/status", json={"status": "waiting"}, headers=h)
    assert appt_status() == "arrived"
    client.post(f"/api/queue/{entry.id}/status", json={"status": "left"}, headers=h)
    assert appt_status() == "arrived"  # leaving says nothing about the appointment


def test_a_cancelled_appointment_does_not_follow_the_queue(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, make_queue_entry: Factory, as_user: Factory, db: Any
) -> None:
    pat = make_patient(lac)
    appt = make_appointment(pat, status="cancelled")
    entry = make_queue_entry(lac, 1, patient_id=pat.id, appointment_id=appt.id, name="X")
    client.post(f"/api/queue/{entry.id}/status", json={"status": "done"}, headers=as_user(lac, "assistant"))
    with db.connect() as conn:
        assert conn.execute(select(appointment.c.status)).scalar_one() == "cancelled"


def _status_of(db: Any, appointment_id: int) -> str:
    with db.connect() as conn:
        return conn.execute(select(appointment.c.status).where(appointment.c.id == appointment_id)).scalar_one()


def _overdue(client: TestClient, h: dict[str, str]) -> tuple[list[int], int]:
    listed = [a["id"] for a in client.get("/api/appointments/overdue", headers=h).json()]
    return listed, client.get("/api/badges", headers=h).json()["overdue"]


def test_a_ticket_for_a_patient_with_an_appointment_today_is_their_arrival(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory, db: Any, clock: Any
) -> None:
    """Code review M4: the ticket taken in the waiting room is the appointment's arrival – never "Non venu ?"."""
    pat = make_patient(lac)
    clock.set(at(FRI, "08:55"))
    appt = make_appointment(pat, starts_at=at(FRI, "09:00"), status="confirmed")
    make_appointment(pat, starts_at=at(SAT, "09:00"))  # another day
    h = as_user(lac, "assistant")
    ticket = client.post("/api/queue", json={"patientId": pat.id}, headers=h).json()
    assert (ticket["appointmentId"], ticket["appointmentAt"]) == (appt.id, "2026-10-30T09:00:00+01:00")
    assert _status_of(db, appt.id) == "arrived"
    client.post(f"/api/queue/{ticket['id']}/status", json={"status": "done"}, headers=h)
    assert _status_of(db, appt.id) == "done"
    clock.set(at(FRI, "09:50"))
    assert _overdue(client, h) == ([], 0)


def test_patients_in_the_waiting_room_are_not_overdue(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory, clock: Any
) -> None:
    pat = make_patient(lac)
    h = as_user(lac, "assistant")
    ticket = client.post("/api/queue", json={"patientId": pat.id}, headers=h).json()  # before the appointment existed
    appt = make_appointment(pat, starts_at=at(FRI, "09:05"), duration_min=30)
    clock.set(at(FRI, "09:55"))
    assert _overdue(client, h) == ([], 0)
    client.post(f"/api/queue/{ticket['id']}/status", json={"status": "left"}, headers=h)
    assert _overdue(client, h) == ([appt.id], 1)


def test_a_patient_who_left_before_the_visit_is_in_the_day_closing(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, as_user: Factory, db: Any, clock: Any
) -> None:
    """Code review N3: "Parti" left the appointment "arrivé" for good – the day closing asks: absent or came?"""
    pat = make_patient(lac)
    appt = make_appointment(pat, starts_at=at(FRI, "09:10"), duration_min=30)
    h = as_user(lac, "assistant")
    client.post(f"/api/appointments/{appt.id}/status", json={"status": "arrived"}, headers=h)
    ticket = client.get("/api/queue", headers=h).json()[0]
    client.post(f"/api/queue/{ticket['id']}/status", json={"status": "left"}, headers=h)
    assert _status_of(db, appt.id) == "arrived"
    clock.set(at(FRI, "09:50"))
    assert _overdue(client, h) == ([], 0)  # not over yet (ended 09:40, + 15 min)
    clock.set(at(FRI, "10:00"))
    assert _overdue(client, h) == ([appt.id], 1)
    assert client.post(f"/api/appointments/{appt.id}/status", json={"status": "no_show"}, headers=h).status_code == 200
    assert _overdue(client, h) == ([], 0)


# --- public pages -------------------------------------------------------------------------------------------------

SECRET_NAME = "Zeineb Secretnom"
SECRET_PHONE = "+21655443322"


@pytest.fixture
def busy(client: TestClient, lac: Any, make_patient: Factory, as_user: Factory, clock: Any) -> list[dict[str, Any]]:
    h = as_user(lac, "assistant")
    pat = make_patient(lac, first_name="Zeineb", last_name="Secretnom", phone=SECRET_PHONE, alerts="Diabète secret")
    entries = [client.post("/api/queue", json={"patientId": pat.id}, headers=h).json()]
    entries += [client.post("/api/queue", json={"name": f"Nom{i} Visible", "phone": "+2162000000" + str(i)}, headers=h).json() for i in range(2, 9)]
    for n in (1, 2, 3, 4):
        clock.advance(minutes=1)
        client.post(f"/api/queue/{entries[n - 1]['id']}/status", json={"status": "called" if n != 2 else "in_treatment"}, headers=h)
    client.post(f"/api/queue/{entries[0]['id']}/status", json={"status": "done"}, headers=h)
    return entries


def test_waiting_room_screen(client: TestClient, lac: Any, busy: list[dict[str, Any]]) -> None:
    res = client.get(f"/api/public/display/{lac.display_token}")
    assert res.status_code == 200, res.text
    assert res.json() == {"practiceName": "Cabinet du Lac", "called": [4, 3, 2], "next": [5, 6, 7, 8], "waiting": 4}


def test_the_screen_shows_at_most_three_calls(client: TestClient, lac: Any, busy: list[dict[str, Any]], as_user: Factory, clock: Any) -> None:
    clock.advance(minutes=1)
    client.post(f"/api/queue/{busy[4]['id']}/status", json={"status": "called"}, headers=as_user(lac, "assistant"))
    body = client.get(f"/api/public/display/{lac.display_token}").json()
    assert (body["called"], body["next"], body["waiting"]) == ([5, 4, 3], [6, 7, 8], 3)


def test_ticket_page(client: TestClient, lac: Any, busy: list[dict[str, Any]]) -> None:
    res = client.get(f"/api/public/ticket/{busy[6]['ticketToken']}")
    assert res.status_code == 200, res.text
    assert res.json() == {
        "practiceName": "Cabinet du Lac", "practicePhone": "+21671000111", "ticketNo": 7, "status": "waiting",
        "position": 3, "peopleAhead": 4, "estimatedWaitMin": 80, "day": "2026-10-30",
    }
    done = client.get(f"/api/public/ticket/{busy[0]['ticketToken']}").json()
    assert (done["status"], done["position"], done["peopleAhead"], done["estimatedWaitMin"]) == ("done", None, 0, 0)


def test_public_pages_never_show_names_phones_or_alerts(client: TestClient, lac: Any, busy: list[dict[str, Any]]) -> None:
    pages = [client.get(f"/api/public/display/{lac.display_token}").text]
    pages += [client.get(f"/api/public/ticket/{e['ticketToken']}").text for e in busy]
    for text in pages:
        for secret in ("Zeineb", "Secretnom", "Visible", "55443322", "2000000", "Diabète", "patient", "name\"", "phone\""):
            assert secret not in text, (secret, text)


def test_unknown_or_old_tokens_are_404(client: TestClient, lac: Any, as_user: Factory, busy: list[dict[str, Any]]) -> None:
    assert_problem(client.get("/api/public/display/" + "0" * 32), 404, "not_found")
    assert_problem(client.get("/api/public/ticket/" + "0" * 32), 404, "not_found")
    client.post("/api/practice/display-token", headers=as_user(lac, "owner"))
    assert_problem(client.get(f"/api/public/display/{lac.display_token}"), 404, "not_found")  # the old screen link


def test_the_screen_shows_only_today(client: TestClient, lac: Any, busy: list[dict[str, Any]], clock: Any) -> None:
    clock.set(at(SAT, "08:00"))
    assert client.get(f"/api/public/display/{lac.display_token}").json() == {
        "practiceName": "Cabinet du Lac", "called": [], "next": [], "waiting": 0}


def test_public_queue_pages_are_rate_limited_per_ip(client: TestClient, lac: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(queue_module, "PUBLIC_LIMIT", 3)
    ip = {"X-Forwarded-For": "203.0.113.50"}
    for _ in range(3):
        assert client.get(f"/api/public/display/{lac.display_token}", headers=ip).status_code == 200
    assert_problem(client.get(f"/api/public/display/{lac.display_token}", headers=ip), 429, "too_many_requests")
    assert_problem(client.get("/api/public/ticket/" + "0" * 32, headers=ip), 429, "too_many_requests")
    assert client.get(f"/api/public/display/{lac.display_token}", headers={"X-Forwarded-For": "203.0.113.51"}).status_code == 200
