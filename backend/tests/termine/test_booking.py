"""Online booking for patients (backlog C1, section 11.3): public profile, slots, bookings, the patient's own link."""

from __future__ import annotations

import hashlib
import itertools
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from daftar import booking as booking_module
from daftar import scheduling
from daftar.tables import appointment, patient, practice
from tests.helpers import assert_problem
from tests.termine.conftest import FRI, MON, SAT, SUN, TUE, Factory, at, iso

_ips = itertools.count(1)


def fresh_ip() -> dict[str, str]:
    """Each booking from its own IP unless a test is about the per-IP limit (20 attempts per hour)."""
    return {"X-Forwarded-For": f"198.51.100.{next(_ips) % 250 + 1}"}


@pytest.fixture
def lac(make_practice: Factory, make_service: Factory) -> Any:
    p = make_practice(
        "Cabinet du Lac", slug="cabinet-lac", specialty="dentiste", practitioners=["Dr. A", "Dr. B"],
        name_ar="عيادة البحيرة", phone="+21671000111", whatsapp="+21620000111", city="Tunis", governorate="tunis",
        address="Rue du Lac", maps_url="https://maps.app.goo.gl/lac", description_fr="Cabinet familial", email="cab@lac.tn",
        tax_id="1234567A", admin_notes="client difficile", contact_name="Mme Gérante", brand_color="#1d4ed8",
        online_booking_enabled=True,
    )
    p.consultation = make_service(p, "Consultation", 30, name_ar="معاينة", online_bookable=True, sort=1, price_millimes=40_000)
    p.scaling = make_service(p, "Détartrage", 45, online_bookable=True, sort=2)
    p.surgery = make_service(p, "Extraction", 30, online_bookable=False, sort=3)
    p.old = make_service(p, "Ancien", 30, online_bookable=True, active=False, sort=4)
    return p


def book(client: TestClient, slug: str, headers: dict[str, str] | None = None, **override: Any) -> Any:
    body = {"serviceId": None, "startsAt": iso(MON, "09:00"), "firstName": "Amira", "lastName": "Ben Ali",
            "phone": "20 111 222", "lang": "ar", "reminderConsent": True, "note": "Dent sensible", "website": ""}
    body.update(override)
    return client.post(f"/api/public/practices/{slug}/bookings", json=body, headers=headers or fresh_ip())


def slot_times(client: TestClient, slug: str, **params: Any) -> list[str]:
    res = client.get(f"/api/public/practices/{slug}/slots", params=params, headers=fresh_ip())
    assert res.status_code == 200, res.text
    assert res.json()["date"] == params["date"]
    return res.json()["slots"]


# --- profile ---------------------------------------------------------------------------------------------------


def test_public_profile(client: TestClient, lac: Any, make_practitioner: Factory) -> None:
    make_practitioner(lac, "Dr. Pas en ligne", online_bookable=False)
    make_practitioner(lac, "Dr. Parti", active=False)
    res = client.get("/api/public/practices/cabinet-lac")
    assert res.status_code == 200, res.text
    body = res.json()
    a, b = lac.practitioners
    assert body == {
        "slug": "cabinet-lac", "name": "Cabinet du Lac", "nameAr": "عيادة البحيرة", "specialty": "dentiste",
        "brandColor": "#1d4ed8", "address": "Rue du Lac", "postalCode": "", "city": "Tunis", "governorate": "tunis",
        "phone": "+21671000111", "whatsapp": "+21620000111", "mapsUrl": "https://maps.app.goo.gl/lac",
        "descriptionFr": "Cabinet familial", "descriptionAr": "", "weeklyHours": body["weeklyHours"],
        "onlineBookingEnabled": True, "horizonDays": 30, "minNoticeHours": 2, "isDemo": False,
        "services": [
            {"id": lac.consultation.id, "nameFr": "Consultation", "nameAr": "معاينة", "durationMin": 30, "priceMillimes": 40_000},
            {"id": lac.scaling.id, "nameFr": "Détartrage", "nameAr": "", "durationMin": 45, "priceMillimes": None},
        ],
        "practitioners": [{"id": a.id, "name": "Dr. A", "title": "Dr.", "specialty": None},
                          {"id": b.id, "name": "Dr. B", "title": "Dr.", "specialty": None}],
    }
    assert body["weeklyHours"]["1"] == [["08:00", "12:30"], ["14:00", "18:00"]]
    for private in ("client difficile", "cab@lac.tn", "1234567A", "Gérante", lac.display_token):
        assert private not in res.text


def test_the_profile_exists_without_online_booking(client: TestClient, make_practice: Factory) -> None:
    make_practice("Cabinet Fermé", slug="cabinet-ferme")
    body = client.get("/api/public/practices/cabinet-ferme").json()
    assert body["onlineBookingEnabled"] is False and body["name"] == "Cabinet Fermé"


@pytest.mark.parametrize("status", ["suspended", "canceled"])
def test_closed_accounts_have_no_public_page(client: TestClient, make_practice: Factory, status: str) -> None:
    make_practice(slug="cabinet-x", status=status, online_booking_enabled=True)
    assert_problem(client.get("/api/public/practices/cabinet-x"), 404, "not_found")
    assert_problem(client.get(f"/api/public/practices/cabinet-x/slots?date={MON}&serviceId=1"), 404, "not_found")


def test_unknown_slugs(client: TestClient) -> None:
    assert_problem(client.get("/api/public/practices/inconnu"), 404, "not_found")
    assert_problem(client.get("/api/public/practices/A_B"), 404, "not_found")


def test_profile_and_slots_are_rate_limited(client: TestClient, lac: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(booking_module, "READ_LIMIT", 2)
    ip = {"X-Forwarded-For": "203.0.113.70"}
    assert client.get("/api/public/practices/cabinet-lac", headers=ip).status_code == 200
    assert client.get(f"/api/public/practices/cabinet-lac/slots?date={MON}&serviceId={lac.consultation.id}", headers=ip).status_code == 200
    assert_problem(client.get("/api/public/practices/cabinet-lac", headers=ip), 429, "too_many_requests")


# --- slots -----------------------------------------------------------------------------------------------------


def test_slots_of_a_day(client: TestClient, lac: Any) -> None:
    got = slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=lac.consultation.id)
    assert got[:3] == ["08:00", "08:15", "08:30"] and got[-1] == "17:30" and "12:00" in got and "12:15" not in got
    long = slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=lac.scaling.id)
    assert "11:45" in long and "12:00" not in long  # 45 minutes before the lunch break


def test_slots_respect_notice_horizon_and_closed_days(client: TestClient, lac: Any, as_user: Factory) -> None:
    s = lac.consultation.id
    assert slot_times(client, "cabinet-lac", date=FRI.isoformat(), serviceId=s)[0] == "11:00"  # now 09:00 + 2 h notice
    assert slot_times(client, "cabinet-lac", date="2026-10-29", serviceId=s) == []
    assert slot_times(client, "cabinet-lac", date="2026-11-28", serviceId=s) != []  # Saturday, 29 days ahead
    assert slot_times(client, "cabinet-lac", date="2026-11-30", serviceId=s) == []  # Monday, 31 days ahead
    assert slot_times(client, "cabinet-lac", date=SUN.isoformat(), serviceId=s) == []
    client.post("/api/closures", json={"startsOn": TUE.isoformat()}, headers=as_user(lac, "owner"))
    assert slot_times(client, "cabinet-lac", date=TUE.isoformat(), serviceId=s) == []


def test_the_horizon_counts_tunis_days(client: TestClient, lac: Any, db: Any, clock: Any) -> None:
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_horizon_days=3, booking_min_notice_hours=0))
    s = lac.consultation.id
    clock.set(at(FRI, "23:50"))
    assert slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=s) != []
    assert slot_times(client, "cabinet-lac", date=TUE.isoformat(), serviceId=s) == []
    clock.set(at(SAT, "00:10"))  # Friday 23:10 UTC – already Saturday in Tunis
    assert slot_times(client, "cabinet-lac", date=TUE.isoformat(), serviceId=s) != []


def test_the_horizon_is_days_from_today_also_for_a_booking(client: TestClient, lac: Any, db: Any) -> None:
    """Code review N9: horizon N = today and the next N days – the web's day strip shows exactly these (N + 1)."""
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_horizon_days=3))
    s = lac.consultation.id
    assert book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "17:00")).status_code == 201  # today + 3
    assert_problem(book(client, "cabinet-lac", serviceId=s, startsAt=iso(TUE, "09:00"), phone="20 999 888"), 422, "outside_horizon")


def test_slots_leave_out_booked_times(client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory) -> None:
    a, b = lac.practitioners
    make_appointment(make_patient(lac), practitioner_id=a.id, starts_at=at(MON, "09:00"))
    s = lac.consultation.id
    assert "09:00" in slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=s)  # Dr. B is free
    assert "09:00" not in slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=s, practitionerId=a.id)
    make_appointment(make_patient(lac), practitioner_id=b.id, starts_at=at(MON, "09:00"))
    assert "09:00" not in slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=s)


def test_a_full_day_offers_nothing(client: TestClient, lac: Any, db: Any, make_patient: Factory, make_appointment: Factory) -> None:
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_max_per_day=1))
    make_appointment(make_patient(lac), starts_at=at(MON, "16:00"), source="online", status="requested")
    make_appointment(make_patient(lac), starts_at=at(TUE, "16:00"), source="online", status="cancelled")
    s = lac.consultation.id
    assert slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=s) == []
    assert slot_times(client, "cabinet-lac", date=TUE.isoformat(), serviceId=s) != []


def test_only_online_practitioners_and_services(client: TestClient, lac: Any, make_practitioner: Factory) -> None:
    hidden = make_practitioner(lac, "Dr. Caché", online_bookable=False)
    url = "/api/public/practices/cabinet-lac/slots"
    assert_problem(client.get(url, params={"date": MON.isoformat(), "serviceId": lac.surgery.id}), 422, "invalid_service")
    assert_problem(client.get(url, params={"date": MON.isoformat(), "serviceId": lac.old.id}), 422, "invalid_service")
    assert_problem(client.get(url, params={"date": MON.isoformat(), "serviceId": 999999}), 422, "invalid_service")
    res = client.get(url, params={"date": MON.isoformat(), "serviceId": lac.consultation.id, "practitionerId": hidden.id})
    assert_problem(res, 422, "invalid_practitioner")
    assert_problem(client.get(url, params={"date": MON.isoformat()}), 422, "validation")


def test_a_practice_without_practitioners_books_its_one_calendar(client: TestClient, make_practice: Factory, make_service: Factory) -> None:
    p = make_practice(slug="solo", online_booking_enabled=True)
    s = make_service(p, online_bookable=True)
    assert slot_times(client, "solo", date=MON.isoformat(), serviceId=s.id)[0] == "08:00"
    res = book(client, "solo", serviceId=s.id)
    assert res.status_code == 201, res.text
    assert res.json()["practitionerName"] is None
    assert "09:00" not in slot_times(client, "solo", date=MON.isoformat(), serviceId=s.id)


def test_disabled_booking(client: TestClient, make_practice: Factory, make_service: Factory) -> None:
    p = make_practice(slug="sans-rdv")
    s = make_service(p, online_bookable=True)
    assert_problem(client.get(f"/api/public/practices/sans-rdv/slots?date={MON}&serviceId={s.id}"), 404, "booking_disabled")
    assert_problem(book(client, "sans-rdv", serviceId=s.id), 404, "booking_disabled")


# --- booking -----------------------------------------------------------------------------------------------------


def test_book_as_a_new_patient(client: TestClient, lac: Any, as_user: Factory, db: Any) -> None:
    res = book(client, "cabinet-lac", serviceId=lac.consultation.id)
    assert res.status_code == 201, res.text
    body = res.json()
    token = body.pop("manageToken")
    assert len(token) >= 40
    assert body == {"status": "requested", "startsAt": iso(MON, "09:00"), "endsAt": iso(MON, "09:30"),
                    "serviceName": "معاينة", "practitionerName": "Dr. A"}  # booked in Arabic (code review N8)
    with db.connect() as conn:
        pat = conn.execute(select(patient)).one()
        appt = conn.execute(select(appointment)).one()
    assert (pat.first_name, pat.last_name, pat.phone, pat.lang, pat.reminder_consent) == ("Amira", "Ben Ali", "+21620111222", "ar", True)
    assert (appt.source, appt.status, appt.patient_note, appt.reason, appt.created_by) == ("online", "requested", "Dent sensible", "Consultation", None)
    assert appt.booking_token_hash == hashlib.sha256(token.encode()).hexdigest()
    staff = client.get("/api/appointments?from=2026-11-02&to=2026-11-02&status=requested", headers=as_user(lac, "assistant")).json()
    assert [(a["source"], a["patientNote"], a["patient"]["lastName"]) for a in staff] == [("online", "Dent sensible", "Ben Ali")]
    assert 'daftar_appointments_created_total{source="online"} 1.0' in client.get("/metrics").text


def test_auto_confirm_and_free_practitioner(client: TestClient, lac: Any, db: Any, make_patient: Factory, make_appointment: Factory) -> None:
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(online_auto_confirm=True))
    make_appointment(make_patient(lac), practitioner_id=lac.practitioners[0].id, starts_at=at(MON, "09:00"))
    body = book(client, "cabinet-lac", serviceId=lac.consultation.id).json()
    assert (body["status"], body["practitionerName"]) == ("confirmed", "Dr. B")


def test_the_profile_of_a_demo_says_so(client: TestClient, make_practice: Factory, clock: Any) -> None:
    """Security review N3: the booking page of a demo shows a clear demo banner (and noindex)."""
    make_practice("Cabinet Dentaire Démo", slug="demo-abcd1234", online_booking_enabled=True, is_demo=True,
                  demo_expires_at=clock.now() + timedelta(hours=24))
    res = client.get("/api/public/practices/demo-abcd1234")
    assert res.status_code == 200, res.text
    assert res.json()["isDemo"] is True


def test_a_phone_typed_with_arabic_digits_is_booked(client: TestClient, lac: Any, db: Any) -> None:
    """Security review N1: Arabic keyboards type "٢٠ ١١١ ٢٢٢" – it used to end in a 500 at the database."""
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id, phone="٢٠ ١١١ ٢٢٢").status_code == 201
    with db.connect() as conn:
        assert conn.execute(select(patient.c.phone)).scalar_one() == "+21620111222"


def test_a_returning_patient_is_recognized_by_phone_and_last_name(
    client: TestClient, lac: Any, make_patient: Factory, db: Any
) -> None:
    known = make_patient(lac, first_name="Amira", last_name="BEN ALI", phone="+21620111222", lang="fr", reminder_consent=False)
    make_patient(lac, first_name="Sami", last_name="Ben Ali", phone="+21629999999")  # same name, other phone
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id, lastName=" ben ali ").status_code == 201
    with db.connect() as conn:
        assert conn.execute(select(appointment.c.patient_id)).scalar_one() == known.id
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 2
        assert conn.execute(select(patient.c.lang).where(patient.c.id == known.id)).scalar_one() == "fr"  # unchanged
    # the daughter shares the phone but has another last name → her own record
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id, startsAt=iso(MON, "10:00"), firstName="Lina",
                lastName="Trabelsi").status_code == 201
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 3


def test_patients_who_did_not_come_are_blocked(client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, db: Any, clock: Any) -> None:
    mother = make_patient(lac, last_name="Ben Ali", phone="+21620111222")
    son = make_patient(lac, last_name="Kefi", phone="+21620111222")
    make_appointment(mother, starts_at=clock.now() - timedelta(days=30), status="no_show")
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id).status_code == 201  # one no-show: fine
    make_appointment(son, starts_at=clock.now() - timedelta(days=20), status="no_show")
    res = book(client, "cabinet-lac", serviceId=lac.consultation.id, startsAt=iso(MON, "11:00"), lastName="Nouveau")
    assert_refused(res)
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_block_no_shows=0))
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id, startsAt=iso(MON, "11:00")).status_code == 201


def test_at_most_two_future_online_bookings_per_phone(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, clock: Any
) -> None:
    pat = make_patient(lac, last_name="Ben Ali", phone="+21620111222")
    make_appointment(pat, starts_at=clock.now() - timedelta(days=3), source="online", status="done")
    make_appointment(pat, starts_at=at(TUE, "09:00"), source="online", status="cancelled")
    make_appointment(pat, starts_at=at(TUE, "10:00"), source="staff")
    s = lac.consultation.id
    assert book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:00")).status_code == 201
    assert book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "10:00")).status_code == 201
    assert_refused(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "11:00")))


def assert_refused(res: Any) -> None:
    """Security review M1: every refusal that depends on the person is one and the same answer."""
    body = assert_problem(res, 422, "booking_refused")
    assert body["detail"] == "Merci d'appeler le cabinet pour prendre rendez-vous."
    assert set(body) == {"type", "title", "status", "detail", "code"}


def test_personal_refusals_are_one_answer_and_come_after_the_slot_check(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, clock: Any, db: Any
) -> None:
    """Security review M1: the booking form is no oracle for "is this number a (no-show) patient here?". A time that
    is not free answers 409 for everybody; only a free time reaches the checks per person, and those all answer the
    same – no-shows, two future online bookings, or the known patient already has an appointment then. Nothing is
    stored."""
    s = lac.consultation.id
    blocked = make_patient(lac, last_name="Kefi", phone="+21620111222")
    make_appointment(blocked, starts_at=clock.now() - timedelta(days=30), status="no_show")
    make_appointment(blocked, starts_at=clock.now() - timedelta(days=20), status="no_show")
    busy = make_patient(lac, last_name="Gharbi", phone="+21620333444")
    make_appointment(busy, starts_at=at(MON, "11:00"), source="staff", practitioner_id=lac.practitioners[0].id)
    full = make_patient(lac, last_name="Jlassi", phone="+21620555666")
    for hhmm in ("09:00", "10:00"):
        make_appointment(full, starts_at=at(TUE, hhmm), source="online")
    with db.connect() as conn:
        before = conn.execute(select(func.count()).select_from(appointment)).scalar_one()

    # off the grid (03:07 is inside the booking window): the same 409 as for a stranger, whoever the number is
    for phone in ("20 111 222", "20 555 666", "20 999 999"):
        assert_problem(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:07"), phone=phone, lastName="X"),
                       409, "slot_unavailable")
    # a free time: one answer for every reason that depends on the person
    assert_refused(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:30"), phone="20 111 222"))
    assert_refused(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:30"), phone="20 555 666"))
    assert_refused(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "11:00"), phone="20 333 444",
                        lastName="gharbi"))  # Dr. B is free at 11:00, the patient is not
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == before
    # somebody else with the same number but another name is a new patient: booked
    assert book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "11:00"), phone="20 333 444",
                lastName="Autre").status_code == 201


def test_booking_max_per_day(client: TestClient, lac: Any, db: Any) -> None:
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_max_per_day=1))
    s = lac.consultation.id
    assert book(client, "cabinet-lac", serviceId=s).status_code == 201
    assert_problem(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "15:00"), phone="20 333 444", lastName="Autre"),
                   429, "day_full")
    assert book(client, "cabinet-lac", serviceId=s, startsAt=iso(TUE, "15:00"), phone="20 333 444", lastName="Autre").status_code == 201


def test_twenty_booking_attempts_per_ip_and_hour(client: TestClient, lac: Any, clock: Any) -> None:
    """Patients behind a mobile carrier's NAT share one IP (fixlist 2): 20 attempts per IP and hour, bots included."""
    ip = {"X-Forwarded-For": "203.0.113.90"}
    s = lac.consultation.id
    for n, hhmm in enumerate(("09:00", "10:00")):
        res = book(client, "cabinet-lac", ip, serviceId=s, startsAt=iso(MON, hhmm), phone=f"20 00{n} 111", lastName=f"P{n}")
        assert res.status_code == 201, res.text
    for _ in range(18):
        assert book(client, "cabinet-lac", ip, serviceId=s, website="http://spam.example").status_code == 201
    res = book(client, "cabinet-lac", ip, serviceId=s, startsAt=iso(MON, "14:00"), phone="20 009 111", lastName="P9")
    assert_problem(res, 429, "too_many_requests")
    assert int(res.headers["Retry-After"]) > 0
    clock.advance(hours=1)
    assert book(client, "cabinet-lac", ip, serviceId=s, startsAt=iso(MON, "14:00"), phone="20 009 111", lastName="P9").status_code == 201


def test_three_booking_attempts_per_phone_and_practice_and_hour(
    client: TestClient, lac: Any, clock: Any, make_practice: Factory, make_service: Factory
) -> None:
    s = lac.consultation.id
    for _ in range(3):  # failed attempts count as well (09:07 is not on the grid), each from another IP
        assert_problem(book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:07")), 409, "slot_unavailable")
    res = book(client, "cabinet-lac", serviceId=s, phone="+216 20 111 222")  # the same number, written differently
    assert_problem(res, 429, "too_many_requests")
    assert int(res.headers["Retry-After"]) > 0
    assert book(client, "cabinet-lac", serviceId=s, phone="20 111 333", lastName="Autre").status_code == 201
    other = make_practice("Cabinet de la Mer", slug="cabinet-mer", practitioners=["Dr. M"], online_booking_enabled=True)
    svc = make_service(other, "Consultation", 30, online_bookable=True)
    assert book(client, "cabinet-mer", serviceId=svc.id).status_code == 201  # the same number in another practice
    clock.advance(hours=1)
    assert book(client, "cabinet-lac", serviceId=s).status_code == 201


def meet_before_the_slot_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parallel bookings wait for each other right at the slot check, before the limits per phone and per day are
    read - without a lock both would pass them. A request that waits for the other one's lock never arrives: the first
    goes on alone."""
    barrier = threading.Barrier(2)
    real = booking_module._free

    def meet(*args: Any, **kwargs: Any) -> Any:
        try:
            barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            pass
        return real(*args, **kwargs)

    monkeypatch.setattr(booking_module, "_free", meet)


def in_parallel(*calls: Callable[[], Any]) -> list[Any]:
    with ThreadPoolExecutor(len(calls)) as pool:
        return [f.result() for f in [pool.submit(c) for c in calls]]


def test_two_future_bookings_per_phone_hold_under_parallel_requests(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, monkeypatch: pytest.MonkeyPatch, db: Any
) -> None:
    pat = make_patient(lac, last_name="Ben Ali", phone="+21620111222")
    make_appointment(pat, starts_at=at(TUE, "09:00"), source="online")
    meet_before_the_slot_check(monkeypatch)
    s = lac.consultation.id
    results = in_parallel(lambda: book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:00")),
                          lambda: book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "10:00")))
    assert sorted(r.status_code for r in results) == [201, 422], [r.text for r in results]
    assert_refused(next(r for r in results if r.status_code == 422))
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 2


def test_booking_max_per_day_holds_under_parallel_requests(
    client: TestClient, lac: Any, db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == lac.id).values(booking_max_per_day=1))
    meet_before_the_slot_check(monkeypatch)
    s = lac.consultation.id
    results = in_parallel(
        lambda: book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "09:00")),
        lambda: book(client, "cabinet-lac", serviceId=s, startsAt=iso(MON, "10:00"), phone="20 333 444", lastName="Autre"),
    )
    assert sorted(r.status_code for r in results) == [201, 429], [r.text for r in results]
    assert_problem(next(r for r in results if r.status_code == 429), 429, "day_full")
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 1


def test_the_honeypot_pretends_and_stores_nothing(client: TestClient, lac: Any, db: Any) -> None:
    res = book(client, "cabinet-lac", serviceId=lac.consultation.id, website="http://spam.example")
    assert res.status_code == 201 and res.json()["status"] == "requested" and res.json()["manageToken"]
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(appointment)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 0
    assert_problem(lookup(client, res.json()["manageToken"]), 404, "not_found")


@pytest.mark.parametrize(
    ("override", "status", "code"),
    [
        ({"startsAt": iso(MON, "09:07")}, 409, "slot_unavailable"),  # not on the grid
        ({"startsAt": iso(SUN, "09:00")}, 409, "slot_unavailable"),
        ({"startsAt": iso(MON, "12:15")}, 409, "slot_unavailable"),  # into the lunch break
        ({"startsAt": iso(FRI, "10:30")}, 422, "too_soon"),  # less than 2 h ahead
        ({"startsAt": iso(FRI, "08:00")}, 422, "too_soon"),
        ({"startsAt": iso(date(2026, 11, 30), "09:00")}, 422, "outside_horizon"),
        ({"startsAt": "2026-11-02T09:00:00"}, 422, "validation"),
        ({"firstName": ""}, 422, "validation"),
        ({"lastName": "x" * 121}, 422, "validation"),
        ({"phone": "123"}, 422, "invalid_phone"),
        ({"phone": "２０ １１１ ２２２"}, 422, "invalid_phone"),  # full-width digits: 422, never a 500 (N1)
        ({"lang": "en"}, 422, "validation"),
        ({"note": "x" * 1001}, 422, "validation"),
        ({"serviceId": "surgery"}, 422, "invalid_service"),
        ({"practitionerId": 999999}, 422, "invalid_practitioner"),
    ],
)
def test_booking_validation(client: TestClient, lac: Any, override: dict[str, Any], status: int, code: str, db: Any) -> None:
    body = {"serviceId": lac.consultation.id, **override}
    if body["serviceId"] == "surgery":
        body["serviceId"] = lac.surgery.id
    assert_problem(book(client, "cabinet-lac", **body), status, code)
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 0


def test_a_taken_slot_is_409(client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory) -> None:
    a = lac.practitioners[0].id
    make_appointment(make_patient(lac), practitioner_id=a, starts_at=at(MON, "09:00"))
    assert_problem(book(client, "cabinet-lac", serviceId=lac.consultation.id, practitionerId=a), 409, "slot_unavailable")


def test_a_race_ends_in_409_without_other_patients_data(
    client: TestClient, lac: Any, make_patient: Factory, make_appointment: Factory, monkeypatch: pytest.MonkeyPatch, db: Any
) -> None:
    """The check still sees the slot free; the database refuses – the patient gets 409, never someone's name."""
    a = lac.practitioners[0].id
    make_appointment(make_patient(lac, first_name="Secret", last_name="Voisin"), practitioner_id=a, starts_at=at(MON, "09:00"))
    real = scheduling.free_starts
    monkeypatch.setattr(scheduling, "free_starts", lambda conn, cal, day, duration, resources, **kw: [(at(MON, "09:00"), list(resources))]
                        if day == MON else real(conn, cal, day, duration, resources, **kw))
    res = book(client, "cabinet-lac", serviceId=lac.consultation.id, practitionerId=a)
    body = assert_problem(res, 409, "slot_unavailable")
    assert "Secret" not in res.text and "Voisin" not in res.text and "conflicts" not in body
    with db.connect() as conn:
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 1  # the new patient was rolled back


def test_the_same_patient_cannot_book_the_same_time_twice(client: TestClient, lac: Any) -> None:
    """Dr. B is still free at 09:00, the patient is not: a reason of the person, so the neutral answer (M1)."""
    assert book(client, "cabinet-lac", serviceId=lac.consultation.id).status_code == 201
    assert_refused(book(client, "cabinet-lac", serviceId=lac.consultation.id))


# --- the patient's link /rdv#<token>: the token only ever travels in a request body (fixlists 3 and 2) -----------


def lookup(client: TestClient, token: str, **kw: Any) -> Any:
    return client.post("/api/public/bookings/lookup", json={"token": token}, **kw)


def cancel(client: TestClient, token: str, **kw: Any) -> Any:
    return client.post("/api/public/bookings/cancel", json={"token": token}, **kw)


def test_view_the_own_booking(client: TestClient, lac: Any) -> None:
    token = book(client, "cabinet-lac", serviceId=lac.consultation.id).json()["manageToken"]
    res = lookup(client, token)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "status": "requested", "startsAt": iso(MON, "09:00"), "endsAt": iso(MON, "09:30"), "serviceName": "معاينة",
        "practitionerName": "Dr. A", "canCancel": True, "cancelUntil": iso(MON, "07:00"),
        "practice": {"slug": "cabinet-lac", "name": "Cabinet du Lac", "nameAr": "عيادة البحيرة", "phone": "+21671000111",
                     "whatsapp": "+21620000111", "address": "Rue du Lac", "city": "Tunis",
                     "mapsUrl": "https://maps.app.goo.gl/lac"},
    }
    for private in ("Amira", "Ben Ali", "111222", "Dent sensible"):
        assert private not in res.text


def test_the_service_is_named_in_the_patients_language(client: TestClient, lac: Any) -> None:
    """Code review N8: the confirmation and /rdv named the act in French for a patient who booked in Arabic."""
    fr = book(client, "cabinet-lac", serviceId=lac.consultation.id, lang="fr", phone="20 333 444", lastName="Gharbi").json()
    assert fr["serviceName"] == "Consultation"
    assert lookup(client, fr["manageToken"]).json()["serviceName"] == "Consultation"
    no_arabic_name = book(client, "cabinet-lac", serviceId=lac.scaling.id, startsAt=iso(MON, "10:00")).json()
    assert no_arabic_name["serviceName"] == "Détartrage"  # no Arabic name in the catalog: the French one
    assert lookup(client, no_arabic_name["manageToken"]).json()["serviceName"] == "Détartrage"


def test_cancel_the_own_booking(client: TestClient, lac: Any) -> None:
    token = book(client, "cabinet-lac", serviceId=lac.consultation.id).json()["manageToken"]
    res = cancel(client, token)
    assert res.status_code == 200, res.text
    assert (res.json()["status"], res.json()["canCancel"]) == ("cancelled", False)
    assert cancel(client, token).json() == res.json()  # twice is fine
    assert lookup(client, token).json()["status"] == "cancelled"
    assert "09:00" in slot_times(client, "cabinet-lac", date=MON.isoformat(), serviceId=lac.consultation.id, practitionerId=lac.practitioners[0].id)


def test_cancelling_too_late_or_after_the_visit(client: TestClient, lac: Any, clock: Any, as_user: Factory) -> None:
    token = book(client, "cabinet-lac", serviceId=lac.consultation.id).json()["manageToken"]
    clock.set(at(MON, "07:01"))  # less than 2 hours before 09:00
    assert lookup(client, token).json()["canCancel"] is False
    assert_problem(cancel(client, token), 409, "too_late")
    other = book(client, "cabinet-lac", serviceId=lac.consultation.id, startsAt=iso(TUE, "09:00"), phone="20 555 666", lastName="X").json()
    staff = as_user(lac, "assistant")
    appt_id = client.get("/api/appointments?from=2026-11-03&to=2026-11-03", headers=staff).json()[0]["id"]
    client.post(f"/api/appointments/{appt_id}/status", json={"status": "confirmed"}, headers=staff)
    assert cancel(client, other["manageToken"]).status_code == 200  # confirmed: still possible
    client.post(f"/api/appointments/{appt_id}/status", json={"status": "scheduled"}, headers=staff)
    clock.set(at(TUE, "09:10"))
    client.post(f"/api/appointments/{appt_id}/status", json={"status": "arrived"}, headers=staff)
    assert_problem(cancel(client, other["manageToken"]), 409, "cannot_cancel")


def test_unknown_booking_links(client: TestClient) -> None:
    assert_problem(lookup(client, "inconnu"), 404, "not_found")
    assert_problem(cancel(client, "inconnu"), 404, "not_found")


def test_the_old_links_with_the_token_in_the_path_are_gone(client: TestClient, lac: Any) -> None:
    """``/rdv/<token>`` put the token into URLs (and logs); no real booking used it yet, so the endpoints went away."""
    token = book(client, "cabinet-lac", serviceId=lac.consultation.id).json()["manageToken"]
    assert_problem(client.get(f"/api/public/bookings/{token}"), 404, "not_found")
    assert_problem(client.post(f"/api/public/bookings/{token}/cancel"), 404, "not_found")
    assert lookup(client, token).json()["status"] == "requested"  # untouched


def test_booking_links_are_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(booking_module, "MANAGE_LIMIT", 3)
    ip = {"X-Forwarded-For": "203.0.113.80"}
    assert_problem(lookup(client, "inconnu", headers=ip), 404, "not_found")
    assert_problem(cancel(client, "inconnu", headers=ip), 404, "not_found")
    assert_problem(lookup(client, "inconnu", headers=ip), 404, "not_found")
    assert_problem(cancel(client, "inconnu", headers=ip), 429, "too_many_requests")
    assert_problem(lookup(client, "inconnu", headers=ip), 429, "too_many_requests")


@pytest.mark.parametrize("body", [{}, {"token": ""}, {"token": "x" * 201}, {"token": 42}])
def test_the_body_token_is_validated(client: TestClient, body: dict[str, Any]) -> None:
    for action in ("lookup", "cancel"):
        assert_problem(client.post(f"/api/public/bookings/{action}", json=body), 422, "validation")
