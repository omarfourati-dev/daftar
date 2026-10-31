"""Appointments (backlog B2, sections 5, 11.1, 15): CRUD, no double bookings (409 + suggestions), overdue, reminder."""

from __future__ import annotations

import itertools
import threading
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from daftar import scheduling
from daftar.tables import appointment
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, SAT, TUE, Factory, at, iso


@pytest.fixture
def lac(make_practice: Factory) -> Any:
    return make_practice("Cabinet du Lac", practitioners=["Dr. A", "Dr. B"])


@pytest.fixture
def ids(lac: Any, make_patient: Factory) -> dict[str, Any]:
    a, b = lac.practitioners
    return {
        "a": a.id, "b": b.id,
        "amira": make_patient(lac, first_name="Amira", last_name="Ben Ali", phone="+21620111222", alerts="Anticoagulant"),
        "karim": make_patient(lac, first_name="Karim", last_name="Trabelsi"),
    }


def book(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    return client.post("/api/appointments", json=body, headers=headers)


def test_create_an_appointment(client: TestClient, lac: Any, ids: dict[str, Any], as_user: Factory, app: Any) -> None:
    res = book(client, as_user(lac, "assistant"), patientId=ids["amira"].id, startsAt=iso(MON, "09:30"),
               practitionerId=ids["a"], reason="Douleur", notes="Préfère le matin", depositRequiredMillimes=20_000)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["conflicts"] == []
    appt = body["appointment"]
    assert appt == {
        "id": appt["id"],
        "patient": {"id": ids["amira"].id, "firstName": "Amira", "lastName": "Ben Ali", "phone": "+21620111222",
                    "noShows": 0, "alerts": "Anticoagulant", "lang": "fr"},
        "practitionerId": ids["a"], "practitionerName": "Dr. A", "serviceId": None, "serviceName": None,
        "startsAt": "2026-11-02T09:30:00+01:00", "endsAt": "2026-11-02T10:00:00+01:00", "durationMin": 30,
        "reason": "Douleur", "status": "scheduled", "source": "staff", "notes": "Préfère le matin", "patientNote": "",
        "depositRequiredMillimes": 20_000, "depositPaidMillimes": 0, "reminderSentAt": None, "seriesId": None,
        "createdAt": "2026-10-30T09:00:00+01:00",
    }
    metrics = client.get("/metrics").text
    assert 'daftar_appointments_created_total{source="staff"} 1.0' in metrics
    assert 'daftar_appointments_created_total{source="online"} 0.0' in metrics


def test_the_patients_language_comes_with_the_appointment(client: TestClient, lac: Any, make_patient: Factory, as_user: Factory) -> None:
    """Fixlist 2: confirmation, refusal and reminder texts go out in the patient's language, not the screen's."""
    salma = make_patient(lac, first_name="Salma", last_name="Ayari", lang="ar")
    h = as_user(lac, "assistant")
    created = book(client, h, patientId=salma.id, startsAt=iso(MON, "11:00")).json()["appointment"]
    assert created["patient"]["lang"] == "ar"
    listed = client.get("/api/appointments?from=2026-11-02&to=2026-11-02", headers=h).json()
    assert [a["patient"]["lang"] for a in listed] == ["ar"]
    assert client.get(f"/api/appointments/{created['id']}", headers=h).json()["patient"]["lang"] == "ar"


def test_a_service_sets_the_duration(client: TestClient, lac: Any, ids: dict[str, Any], make_service: Factory, as_user: Factory) -> None:
    scaling = make_service(lac, "Détartrage", 45)
    h = as_user(lac, "dentist")
    appt = book(client, h, patientId=ids["amira"].id, startsAt=iso(MON, "10:00"), serviceId=scaling.id).json()["appointment"]
    assert (appt["durationMin"], appt["endsAt"], appt["serviceId"], appt["serviceName"]) == (
        45, "2026-11-02T10:45:00+01:00", scaling.id, "Détartrage")
    own = book(client, h, patientId=ids["karim"].id, startsAt=iso(MON, "11:00"), serviceId=scaling.id, durationMin=20).json()
    assert own["appointment"]["durationMin"] == 20
    plain = book(client, h, patientId=ids["karim"].id, startsAt=iso(MON, "14:00")).json()["appointment"]
    assert (plain["durationMin"], plain["practitionerId"], plain["practitionerName"]) == (30, ids["a"], "Dr. A")  # H1: first free


def test_status_confirmed_on_creation(client: TestClient, lac: Any, ids: dict[str, Any], as_user: Factory) -> None:
    res = book(client, as_user(lac, "owner"), patientId=ids["amira"].id, startsAt=iso(MON, "09:00"), status="confirmed")
    assert res.json()["appointment"]["status"] == "confirmed"
    res = book(client, as_user(lac, "owner"), patientId=ids["karim"].id, startsAt=iso(MON, "10:00"), status="done")
    assert_problem(res, 422, "validation")


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"startsAt": "2026-11-02T09:30:00"}, 422, "validation"),  # no offset
        ({"startsAt": "2026-11-02T09:30:30+01:00"}, 422, "invalid_time"),
        ({"durationMin": 4}, 422, "validation"),
        ({"durationMin": 481}, 422, "validation"),
        ({"reason": "x" * 301}, 422, "validation"),
        ({"notes": "x" * 2001}, 422, "validation"),
        ({"depositRequiredMillimes": -1}, 422, "validation"),
        ({"patientId": 999999}, 404, "not_found"),
        ({"practitionerId": 999999}, 404, "not_found"),
        ({"serviceId": 999999}, 404, "not_found"),
        ({"startsAt": iso(MON, "07:30")}, 422, "outside_hours"),
        ({"startsAt": iso(MON, "12:15")}, 422, "outside_hours"),  # would run into the lunch break
        ({"startsAt": iso(MON, "17:45")}, 422, "outside_hours"),
        ({"startsAt": "2026-11-01T10:00:00+01:00"}, 422, "outside_hours"),  # Sunday
        ({"startsAt": iso(FRI, "08:44")}, 422, "in_past"),  # more than 15 minutes ago
    ],
)
def test_create_validation(client: TestClient, lac: Any, ids: dict[str, Any], as_user: Factory, change: dict[str, Any], status: int, code: str, db: Any) -> None:
    body = {"patientId": ids["amira"].id, "startsAt": iso(MON, "09:30"), "practitionerId": ids["a"], **change}
    assert_problem(book(client, as_user(lac, "assistant"), **body), status, code)
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 0


def test_the_running_quarter_hour_can_still_be_booked(client: TestClient, lac: Any, ids: dict[str, Any], as_user: Factory) -> None:
    assert book(client, as_user(lac, "assistant"), patientId=ids["amira"].id, startsAt=iso(FRI, "08:45")).status_code == 201


def test_closing_days_and_inactive_choices(
    client: TestClient, lac: Any, ids: dict[str, Any], make_practitioner: Factory, make_service: Factory, as_user: Factory
) -> None:
    owner = as_user(lac, "owner")
    client.post("/api/closures", json={"startsOn": TUE.isoformat()}, headers=owner)
    assert_problem(book(client, owner, patientId=ids["amira"].id, startsAt=iso(TUE, "09:00")), 422, "closed")
    gone = make_practitioner(lac, "Dr. Parti", active=False)
    assert_problem(book(client, owner, patientId=ids["amira"].id, startsAt=iso(MON, "09:00"), practitionerId=gone.id), 422, "practitioner_inactive")
    old = make_service(lac, "Ancien acte", active=False)
    assert_problem(book(client, owner, patientId=ids["amira"].id, startsAt=iso(MON, "09:00"), serviceId=old.id), 422, "service_inactive")


def test_double_booking_a_practitioner_is_409_with_suggestions(
    client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory
) -> None:
    taken = make_appointment(ids["karim"], practitioner_id=ids["a"], starts_at=at(MON, "09:00"), duration_min=30)
    res = book(client, as_user(lac, "assistant"), patientId=ids["amira"].id, startsAt=iso(MON, "09:15"), practitionerId=ids["a"])
    body = assert_problem(res, 409, "appointment_conflict")
    assert body["conflicts"] == [{"id": taken.id, "startsAt": "2026-11-02T09:00:00+01:00", "endsAt": "2026-11-02T09:30:00+01:00",
                                  "patientName": "Karim Trabelsi"}]
    assert body["suggestions"] == [iso(MON, t) for t in ("09:30", "09:45", "10:00", "10:15", "10:30")]
    other = book(client, as_user(lac, "assistant"), patientId=ids["amira"].id, startsAt=iso(MON, "09:15"), practitionerId=ids["b"])
    assert other.status_code == 201  # the other practitioner is free


def test_a_patient_is_never_booked_twice_at_once(
    client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory
) -> None:
    mine = make_appointment(ids["amira"], practitioner_id=ids["a"], starts_at=at(MON, "09:00"), duration_min=60)
    res = book(client, as_user(lac, "assistant"), patientId=ids["amira"].id, startsAt=iso(MON, "09:30"), practitionerId=ids["b"])
    body = assert_problem(res, 409, "appointment_conflict")
    assert [c["id"] for c in body["conflicts"]] == [mine.id]
    assert body["suggestions"][0] == iso(MON, "10:00")  # free for practitioner B *and* the patient


def test_suggestions_skip_lunch_closures_and_sundays(
    client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory
) -> None:
    owner = as_user(lac, "owner")
    make_appointment(ids["karim"], practitioner_id=ids["a"], starts_at=at(SAT, "17:30"), duration_min=30)
    client.post("/api/closures", json={"startsOn": MON.isoformat()}, headers=owner)
    res = book(client, owner, patientId=ids["amira"].id, startsAt=iso(SAT, "17:30"), practitionerId=ids["a"])
    body = assert_problem(res, 409, "appointment_conflict")
    assert body["suggestions"] == [iso(TUE, t) for t in ("08:00", "08:15", "08:30", "08:45", "09:00")]


def test_suggestions_stay_within_seven_days(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice(weekly_hours={"1": [["09:00", "09:30"]]})  # open half an hour on Mondays only
    make_appointment(make_patient(p), starts_at=at(MON, "09:00"), duration_min=30)
    res = book(client, as_user(p, "owner"), patientId=make_patient(p).id, startsAt=iso(MON, "09:00"))
    assert assert_problem(res, 409, "appointment_conflict")["suggestions"] == []  # next Monday is 7 days away


def test_appointments_without_practitioner_share_one_calendar(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    """Only a practice without active practitioners keeps appointments without one – all in one calendar."""
    p = make_practice()
    h = as_user(p, "assistant")
    make_appointment(make_patient(p), starts_at=at(MON, "09:00"), duration_min=30)
    assert_problem(book(client, h, patientId=make_patient(p).id, startsAt=iso(MON, "09:00")), 409, "appointment_conflict")
    res = book(client, h, patientId=make_patient(p).id, startsAt=iso(MON, "09:30"))
    assert res.status_code == 201, res.text
    assert res.json()["appointment"]["practitionerId"] is None


def test_without_practitioner_the_only_practitioner_is_taken(
    client: TestClient, make_practice: Factory, make_service: Factory, make_patient: Factory, as_user: Factory
) -> None:
    """Code review H1: an appointment "Non attribué" next to the only doctor's calendar was a double booking."""
    p = make_practice(slug="cabinet-x", practitioners=["Dr. X"], online_booking_enabled=True)
    (x,) = p.practitioners
    svc = make_service(p, "Consultation", 30, online_bookable=True)
    h = as_user(p, "assistant")
    res = book(client, h, patientId=make_patient(p).id, startsAt=iso(MON, "09:00"))
    assert res.status_code == 201, res.text
    assert res.json()["appointment"]["practitionerId"] == x.id
    assert_problem(book(client, h, patientId=make_patient(p).id, startsAt=iso(MON, "09:00"), practitionerId=x.id), 409, "appointment_conflict")
    assert_problem(book(client, h, patientId=make_patient(p).id, startsAt=iso(MON, "09:15")), 409, "appointment_conflict")
    slots = client.get("/api/public/practices/cabinet-x/slots", params={"date": MON.isoformat(), "serviceId": svc.id}).json()["slots"]
    assert "09:00" not in slots and "09:30" in slots
    online = client.post("/api/public/practices/cabinet-x/bookings", json={
        "serviceId": svc.id, "startsAt": iso(MON, "09:00"), "firstName": "Amira", "lastName": "Ben Ali", "phone": "20 111 222",
        "lang": "fr", "reminderConsent": False, "website": ""})
    assert_problem(online, 409, "slot_unavailable")
    after_monday = client.get("/api/availability/next", params={"limit": 50}, headers=h).json()
    assert iso(MON, "09:00") not in [s["startsAt"] for s in after_monday]


def test_without_practitioner_the_first_free_one_is_taken(
    client: TestClient, lac: Any, ids: dict[str, Any], make_patient: Factory, as_user: Factory
) -> None:
    h = as_user(lac, "assistant")
    first = book(client, h, patientId=ids["amira"].id, startsAt=iso(MON, "09:00")).json()["appointment"]
    assert first["practitionerId"] == ids["a"]  # practice order
    second = book(client, h, patientId=ids["karim"].id, startsAt=iso(MON, "09:00")).json()["appointment"]
    assert second["practitionerId"] == ids["b"]
    body = assert_problem(book(client, h, patientId=make_patient(lac).id, startsAt=iso(MON, "09:15")), 409, "appointment_conflict")
    assert sorted(c["id"] for c in body["conflicts"]) == sorted([first["id"], second["id"]])
    assert body["suggestions"][0] == iso(MON, "09:30")  # free again for either of them


def test_moving_an_appointment_without_practitioner_gives_it_one(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    p = make_practice(practitioners=["Dr. X"])
    (x,) = p.practitioners
    legacy = make_appointment(make_patient(p), starts_at=at(MON, "09:00"))  # from before the rule
    res = client.patch(f"/api/appointments/{legacy.id}", json={"startsAt": iso(MON, "10:00")}, headers=as_user(p, "assistant"))
    assert res.status_code == 200, res.text
    assert res.json()["appointment"]["practitionerId"] == x.id


def test_a_race_for_the_same_slot_ends_in_409_not_500(
    app: Any, lac: Any, ids: dict[str, Any], as_user: Factory, monkeypatch: pytest.MonkeyPatch, db: Any
) -> None:
    """Both requests pass the API's own check before either inserts; the EXCLUDE constraint decides."""
    barrier = threading.Barrier(2, timeout=10)
    original = scheduling.find_conflicts
    calls = itertools.count()

    def check_then_wait(*args: Any, **kwargs: Any) -> Any:
        found = original(*args, **kwargs)
        if next(calls) < 2:  # the first check of each request
            barrier.wait()
        return found

    monkeypatch.setattr(scheduling, "find_conflicts", check_then_wait)
    h = as_user(lac, "assistant")
    results: list[Any] = []

    def take(patient_id: int) -> None:
        with TestClient(app) as c:
            results.append(book(c, h, patientId=patient_id, startsAt=iso(MON, "09:00"), practitionerId=ids["a"]))

    threads = [threading.Thread(target=take, args=(p.id,)) for p in (ids["amira"], ids["karim"])]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    loser = next(r for r in results if r.status_code == 409)
    body = assert_problem(loser, 409, "appointment_conflict")
    winner = next(r for r in results if r.status_code == 201).json()["appointment"]
    assert [c["id"] for c in body["conflicts"]] == [winner["id"]]
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 1


# --- reading ------------------------------------------------------------------------------------------------------


def test_list_a_range_in_tunis_days(
    client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, make_payment: Factory, as_user: Factory, make_practice: Factory, make_patient: Factory
) -> None:
    late_friday = make_appointment(ids["amira"], starts_at=at(FRI, "23:30"))  # 22:30 UTC
    early_saturday = make_appointment(ids["karim"], starts_at=at(SAT, "00:30"))  # 23:30 UTC on Friday
    monday = make_appointment(ids["amira"], practitioner_id=ids["b"], starts_at=at(MON, "10:00"), status="cancelled")
    make_appointment(make_patient(make_practice()), starts_at=at(SAT, "10:00"))  # another practice
    make_payment(ids["karim"], 15_000, appointment_id=early_saturday.id, is_deposit=True)
    make_payment(ids["karim"], 5_000, appointment_id=early_saturday.id, is_deposit=False)
    h = as_user(lac, "assistant")
    friday = client.get("/api/appointments?from=2026-10-30&to=2026-10-30", headers=h).json()
    assert [a["id"] for a in friday] == [late_friday.id]
    saturday = client.get("/api/appointments?from=2026-10-31&to=2026-10-31", headers=h).json()
    assert [a["id"] for a in saturday] == [early_saturday.id]
    assert saturday[0]["depositPaidMillimes"] == 15_000
    week = client.get("/api/appointments?from=2026-10-30&to=2026-11-05", headers=h).json()
    assert [a["id"] for a in week] == [late_friday.id, early_saturday.id, monday.id]
    assert [a["id"] for a in client.get(f"/api/appointments?from=2026-10-30&to=2026-11-05&practitionerId={ids['b']}", headers=h).json()] == [monday.id]
    assert [a["id"] for a in client.get("/api/appointments?from=2026-10-30&to=2026-11-05&status=cancelled", headers=h).json()] == [monday.id]
    both = client.get("/api/appointments?from=2026-10-30&to=2026-11-05&status=scheduled,cancelled", headers=h).json()
    assert len(both) == 3


def test_list_defaults_to_today(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory) -> None:
    today = make_appointment(ids["amira"], starts_at=at(FRI, "10:00"))
    make_appointment(ids["amira"], starts_at=at(SAT, "10:00"))
    assert [a["id"] for a in client.get("/api/appointments", headers=as_user(lac, "assistant")).json()] == [today.id]


@pytest.mark.parametrize(
    ("query", "code"),
    [("from=2026-11-01&to=2027-01-02", "range_too_long"), ("from=2026-11-02&to=2026-11-01", "invalid_range"),
     ("from=01/11/2026", "validation"), ("status=asleep", "validation")],
)
def test_list_validation(client: TestClient, lac: Any, as_user: Factory, query: str, code: str) -> None:
    assert_problem(client.get(f"/api/appointments?{query}", headers=as_user(lac, "assistant")), 422, code)


def test_sixty_two_days_are_fine(client: TestClient, lac: Any, as_user: Factory) -> None:
    assert client.get("/api/appointments?from=2026-11-01&to=2027-01-01", headers=as_user(lac, "assistant")).status_code == 200


def test_get_one_with_no_show_count(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory, clock: Any) -> None:
    for days in (10, 20):
        make_appointment(ids["amira"], starts_at=clock.now() - timedelta(days=days), status="no_show")
    appt = make_appointment(ids["amira"], starts_at=at(MON, "09:00"))
    res = client.get(f"/api/appointments/{appt.id}", headers=as_user(lac, "dentist"))
    assert res.status_code == 200, res.text
    assert res.json()["patient"]["noShows"] == 2


# --- changing -------------------------------------------------------------------------------------------------------


def test_move_an_appointment(client: TestClient, lac: Any, ids: dict[str, Any], as_user: Factory, make_appointment: Factory) -> None:
    h = as_user(lac, "assistant")
    appt = book(client, h, patientId=ids["amira"].id, startsAt=iso(MON, "09:00"), practitionerId=ids["a"]).json()["appointment"]
    url = f"/api/appointments/{appt['id']}"
    res = client.patch(url, json={"startsAt": iso(MON, "09:15")}, headers=h)  # overlaps only itself
    assert res.status_code == 200, res.text
    assert res.json()["appointment"]["startsAt"] == iso(MON, "09:15") and res.json()["conflicts"] == []
    moved = client.patch(url, json={"practitionerId": None, "durationMin": 45, "notes": "x"}, headers=h).json()["appointment"]
    # null = "the first free one" (code review H1): A, since this appointment does not block itself
    assert (moved["practitionerId"], moved["durationMin"], moved["endsAt"], moved["notes"]) == (ids["a"], 45, iso(MON, "10:00"), "x")
    blocker = make_appointment(ids["karim"], practitioner_id=ids["b"], starts_at=at(MON, "11:00"))
    body = assert_problem(client.patch(url, json={"startsAt": iso(MON, "11:00"), "practitionerId": ids["b"]}, headers=h), 409, "appointment_conflict")
    assert [c["id"] for c in body["conflicts"]] == [blocker.id] and body["suggestions"]
    assert_problem(client.patch(url, json={"startsAt": iso(MON, "12:00")}, headers=h), 422, "outside_hours")
    assert_problem(client.patch(url, json={"startsAt": iso(FRI, "08:00")}, headers=h), 422, "in_past")
    assert_problem(client.patch(url, json={"patientId": 999999}, headers=h), 404, "not_found")
    assert_problem(client.patch(url, json={"startsAt": None}, headers=h), 422, "validation")
    other = client.patch(url, json={"patientId": ids["karim"].id}, headers=h).json()["appointment"]
    assert other["patient"]["id"] == ids["karim"].id


def test_finished_appointments_cannot_be_moved(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory, clock: Any) -> None:
    h = as_user(lac, "assistant")
    done = make_appointment(ids["amira"], starts_at=clock.now() - timedelta(hours=1), status="done")
    assert_problem(client.patch(f"/api/appointments/{done.id}", json={"startsAt": iso(MON, "09:00")}, headers=h), 409, "appointment_locked")
    res = client.patch(f"/api/appointments/{done.id}", json={"notes": "Bien passé", "depositRequiredMillimes": 0}, headers=h)
    assert res.status_code == 200 and res.json()["appointment"]["notes"] == "Bien passé"


def test_delete_an_appointment(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory) -> None:
    appt = make_appointment(ids["amira"], starts_at=at(MON, "09:00"))
    h = as_user(lac, "assistant")
    assert client.delete(f"/api/appointments/{appt.id}", headers=h).status_code == 204
    assert_problem(client.get(f"/api/appointments/{appt.id}", headers=h), 404, "not_found")
    assert_problem(client.delete(f"/api/appointments/{appt.id}", headers=h), 404, "not_found")


def test_mark_the_reminder_as_sent(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory, clock: Any) -> None:
    appt = make_appointment(ids["amira"], starts_at=at(SAT, "09:00"))
    clock.advance(minutes=7)
    res = client.post(f"/api/appointments/{appt.id}/reminder", headers=as_user(lac, "assistant"))
    assert res.status_code == 200, res.text
    assert res.json()["reminderSentAt"] == "2026-10-30T09:07:00+01:00"


def test_overdue_appointments_of_today(client: TestClient, lac: Any, ids: dict[str, Any], make_appointment: Factory, as_user: Factory, clock: Any) -> None:
    clock.set(at(FRI, "11:00"))
    over = make_appointment(ids["amira"], starts_at=at(FRI, "10:00"), duration_min=30)  # ended 10:30
    confirmed = make_appointment(ids["karim"], starts_at=at(FRI, "09:00"), duration_min=30, status="confirmed")
    make_appointment(ids["karim"], starts_at=at(FRI, "10:20"), duration_min=30, practitioner_id=ids["a"])  # ended 10:50: < 15 min
    make_appointment(ids["karim"], starts_at=at(FRI, "08:00"), duration_min=30, status="done")
    make_appointment(ids["karim"], starts_at=at(FRI, "08:30"), duration_min=30, status="arrived")
    make_appointment(ids["amira"], starts_at=at(FRI, "07:00"), duration_min=30, status="no_show")
    make_appointment(ids["amira"], starts_at=at(FRI, "10:00") - timedelta(days=1), duration_min=30)  # yesterday
    res = client.get("/api/appointments/overdue", headers=as_user(lac, "assistant"))
    assert res.status_code == 200, res.text
    assert [a["id"] for a in res.json()] == [confirmed.id, over.id]


def test_appointments_of_another_practice_are_404(
    client: TestClient, lac: Any, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    other = make_practice(practitioners=1)
    foreign = make_appointment(make_patient(other), starts_at=at(MON, "09:00"))
    h = as_user(lac, "owner")
    assert_problem(client.get(f"/api/appointments/{foreign.id}", headers=h), 404, "not_found")
    assert_problem(client.patch(f"/api/appointments/{foreign.id}", json={"notes": "x"}, headers=h), 404, "not_found")
    assert_problem(client.delete(f"/api/appointments/{foreign.id}", headers=h), 404, "not_found")
    assert_problem(client.post(f"/api/appointments/{foreign.id}/status", json={"status": "confirmed"}, headers=h), 404, "not_found")
    assert_problem(client.post(f"/api/appointments/{foreign.id}/reminder", headers=h), 404, "not_found")
    own = make_patient(lac)
    assert_problem(book(client, h, patientId=make_patient(other).id, startsAt=iso(MON, "10:00")), 404, "not_found")
    assert_problem(book(client, h, patientId=own.id, startsAt=iso(MON, "10:00"), practitionerId=other.practitioners[0].id), 404, "not_found")


def test_appointments_need_a_token_and_an_active_subscription(
    client: TestClient, make_practice: Factory, make_patient: Factory, make_appointment: Factory, as_user: Factory
) -> None:
    for method, url in (("get", "/api/appointments"), ("post", "/api/appointments"), ("get", "/api/appointments/overdue")):
        assert_problem(getattr(client, method)(url), 401, "unauthorized")
    assert_problem(client.get("/api/appointments", headers=as_user(role="admin")), 403, "forbidden")
    p = make_practice(status="suspended")
    pat = make_patient(p)
    appt = make_appointment(pat, starts_at=at(MON, "09:00"))
    h = as_user(p, "assistant")
    assert client.get("/api/appointments?from=2026-11-02&to=2026-11-02", headers=h).status_code == 200
    for res in (
        book(client, h, patientId=pat.id, startsAt=iso(MON, "10:00")),
        client.patch(f"/api/appointments/{appt.id}", json={"notes": "x"}, headers=h),
        client.delete(f"/api/appointments/{appt.id}", headers=h),
        client.post(f"/api/appointments/{appt.id}/status", json={"status": "confirmed"}, headers=h),
        client.post(f"/api/appointments/{appt.id}/reminder", headers=h),
    ):
        assert_problem(res, 402, "subscription_suspended")
