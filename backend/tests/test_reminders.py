"""Reminders (section 5): tomorrow's appointments with a ready message in the patient's language."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from daftar.reminders import first_open_day, render_message
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]
#: Saturday 31.10.2026 in Tunis (UTC+1).
TOMORROW_0930 = datetime(2026, 10, 31, 8, 30, tzinfo=UTC)


@pytest.fixture
def practice_row(make_practice: Factory) -> Any:
    return make_practice("Cabinet Lac", name_ar="عيادة البحيرة", phone="71 234 567")


def test_tomorrow_with_messages_in_the_patient_language(
    client: TestClient, practice_row: Any, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    auth_headers: Factory,
) -> None:
    amira = make_patient(practice_row, first_name="Amira", last_name="Trabelsi", phone="+21620123456",
                         lang="fr", reminder_consent=True)
    sami = make_patient(practice_row, first_name="سامي", last_name="بن علي", phone="+21698765432", lang="ar")
    late = make_appointment(amira, starts_at=TOMORROW_0930 + timedelta(hours=5))
    early = make_appointment(sami, starts_at=TOMORROW_0930, status="confirmed")
    res = client.get("/api/reminders", headers=auth_headers(make_user(practice_row, "assistant")))
    assert res.status_code == 200, res.text
    items = res.json()
    assert [i["appointment"]["id"] for i in items] == [early.id, late.id]
    ar, fr = items
    assert (ar["patientLang"], ar["reminderConsent"], ar["phoneDigits"]) == ("ar", False, "21698765432")
    assert ar["message"] == (
        "مرحبا سامي بن علي، نذكّركم بموعدكم يوم 31/10/2026 على الساعة 09:30 في عيادة البحيرة. "
        "في حال تعذّر الحضور، يرجى إعلامنا على الرقم 71 234 567."
    )
    assert (fr["patientLang"], fr["reminderConsent"], fr["phoneDigits"]) == ("fr", True, "21620123456")
    assert fr["message"] == (
        "Bonjour Amira Trabelsi, nous vous rappelons votre rendez-vous le 31/10/2026 à 14:30 au Cabinet Lac. "
        "En cas d'empêchement, merci de nous prévenir au 71 234 567."
    )
    assert fr["appointment"]["patient"]["firstName"] == "Amira"


def test_cancelled_no_show_and_unconfirmed_online_requests_are_left_out(
    client: TestClient, practice_row: Any, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_practice: Factory, auth_headers: Factory,
) -> None:
    pat = make_patient(practice_row)
    keep = make_appointment(pat, starts_at=TOMORROW_0930, status="scheduled")
    for hours, status in ((1, "cancelled"), (2, "no_show"), (3, "requested")):
        make_appointment(pat, starts_at=TOMORROW_0930 + timedelta(hours=hours), status=status)
    make_appointment(pat, starts_at=T0 + timedelta(hours=2))  # today
    make_appointment(pat, starts_at=datetime(2026, 10, 31, 23, 0, tzinfo=UTC))  # Sunday 00:00 in Tunis
    make_appointment(make_patient(make_practice()), starts_at=TOMORROW_0930)  # another practice
    items = client.get("/api/reminders", headers=auth_headers(make_user(practice_row, "owner"))).json()
    assert [i["appointment"]["id"] for i in items] == [keep.id]


def test_another_day_and_sent_marker(
    client: TestClient, practice_row: Any, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    auth_headers: Factory,
) -> None:
    pat = make_patient(practice_row)
    appt = make_appointment(pat, starts_at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC), reminder_sent_at=T0)
    items = client.get("/api/reminders?day=2026-11-02", headers=auth_headers(make_user(practice_row, "dentist"))).json()
    assert [i["appointment"]["id"] for i in items] == [appt.id]
    assert items[0]["appointment"]["reminderSentAt"] == "2026-10-30T09:00:00+01:00"


def test_reminders_need_staff_and_a_valid_day(client: TestClient, make_user: Factory, auth_headers: Factory) -> None:
    assert_problem(client.get("/api/reminders"), 401, "unauthorized")
    assert_problem(client.get("/api/reminders", headers=auth_headers(make_user(role="admin"))), 403, "forbidden")
    assert_problem(client.get("/api/reminders?day=31-10-2026", headers=auth_headers(make_user())), 422, "validation")


def test_templates_only_replace_known_placeholders() -> None:
    values = {"patient": "Amira", "date": "31/10/2026", "time": "09:30", "practice": "Cabinet", "phone": "71"}
    assert render_message("{patient} {unknown} {0} {patient.__class__} {{patient}}", values) == (
        "Amira {unknown} {0} {patient.__class__} {Amira}"
    )
    assert render_message("{phone}{phone}", values) == "7171"
    # a value that itself looks like a placeholder is not expanded again
    assert render_message("{patient} {date}", {**values, "patient": "{date}"}) == "{date} 31/10/2026"


def test_on_saturday_the_reminders_are_for_monday(
    client: TestClient, practice_row: Any, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    auth_headers: Factory, clock: Any,
) -> None:
    """Code review M6: Sunday is closed – Saturday's list (and the dashboard) must hold Monday's appointments."""
    clock.set(datetime(2026, 10, 31, 15, 0, tzinfo=UTC))  # Saturday 16:00 in Tunis
    pat = make_patient(practice_row, reminder_consent=True)
    monday = make_appointment(pat, starts_at=datetime(2026, 11, 2, 8, 0, tzinfo=UTC))
    tuesday = make_appointment(pat, starts_at=datetime(2026, 11, 3, 8, 0, tzinfo=UTC))
    h = auth_headers(make_user(practice_row, "assistant"))
    assert [i["appointment"]["id"] for i in client.get("/api/reminders", headers=h).json()] == [monday.id]
    assert client.get("/api/dashboard", headers=h).json()["remindersPending"] == 1
    owner = auth_headers(make_user(practice_row, "owner"))
    assert client.post("/api/closures", json={"startsOn": "2026-11-02", "label": "Férié"}, headers=owner).status_code == 201
    assert [i["appointment"]["id"] for i in client.get("/api/reminders", headers=h).json()] == [tuesday.id]


def test_the_next_opening_day_skips_days_without_hours_and_closures() -> None:
    hours = {"1": [["08:00", "12:00"]], "3": [["08:00", "12:00"]]}  # Monday and Wednesday only
    saturday = date(2026, 10, 31)
    assert first_open_day(hours, set(), saturday) == date(2026, 11, 2)
    assert first_open_day(hours, {date(2026, 11, 2)}, saturday) == date(2026, 11, 4)
    assert first_open_day({}, set(), saturday) == date(2026, 11, 1)  # never open: tomorrow, as before
