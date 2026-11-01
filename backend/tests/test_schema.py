"""The migration 0001 against daftar/tables.py, plus the constraints that protect tenants and data."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError

from daftar.db import constraint_name
from daftar.hours import DEFAULT_WEEKLY_HOURS
from daftar.tables import (
    ALL_TABLES,
    REFERENCE_TABLES,
    app_user,
    appointment,
    cash_closing,
    invoice,
    metadata,
    patient,
    payment,
    plan,
    practice,
    practice_closure,
    practitioner,
    queue_entry,
    service,
    treatment,
    invitation,
    import_job,
    import_template,
    feedback,
    password_reset,
    audit_log,
    equipment,
    hygiene_task,
    hygiene_task_done,
    hygiene_task_due,
    stock_movement,
    stock_product,
    stock_receipt,
    stock_receipt_line,
    supplier,
    specimen_label_log,
    sterile_pack,
    sterile_pack_use,
    sterilization_cycle,
)

REFLECTED = {"BigInteger": "BIGINT", "Integer": "INTEGER", "Text": "TEXT", "DateTime": "TIMESTAMP",
             "Time": "TIME", "Date": "DATE", "Boolean": "BOOLEAN", "JSONB": "JSONB", "UUID": "UUID",
             "LargeBinary": "BYTEA"}
Factory = Callable[..., Any]


def refused(db: Engine, statement: Any) -> str | None:
    """Runs ``statement`` expecting an IntegrityError; returns the violated constraint's name."""
    with pytest.raises(IntegrityError) as caught, db.begin() as conn:
        conn.execute(statement)
    return constraint_name(caught.value)


def test_tables_py_mirrors_the_migrated_schema(db: Engine) -> None:
    insp = inspect(db)
    assert set(insp.get_table_names()) - {"alembic_version"} == {t.name for t in metadata.sorted_tables}
    assert {t.name for t in (*ALL_TABLES, *REFERENCE_TABLES)} == {t.name for t in metadata.sorted_tables}
    for table in metadata.sorted_tables:
        live = {c["name"]: c for c in insp.get_columns(table.name)}
        assert set(live) == {c.name for c in table.columns}, table.name
        for column in table.columns:
            where = f"{table.name}.{column.name}"
            assert live[column.name]["nullable"] == column.nullable, where
            assert type(live[column.name]["type"]).__name__ == REFLECTED[type(column.type).__name__], where
            if REFLECTED[type(column.type).__name__] == "TIMESTAMP":
                assert live[column.name]["type"].timezone is True, where


def test_plans_are_seeded(db: Engine) -> None:
    with db.connect() as conn:
        rows = conn.execute(select(plan.c.code, plan.c.price_millimes, plan.c.period_months, plan.c.active).order_by(plan.c.price_millimes)).all()
    assert rows == [("pilot", 0, 1, True), ("cabinet_mensuel", 29_000, 1, True), ("cabinet_annuel", 290_000, 12, True)]


def test_practice_defaults(db: Engine) -> None:
    with db.begin() as conn:
        row = conn.execute(
            insert(practice).values(name="Cabinet Test", slug="cabinet-test", specialty="generaliste").returning(practice)
        ).one()
    assert row.weekly_hours == DEFAULT_WEEKLY_HOURS
    assert (row.slot_minutes, row.default_duration_min, row.brand_color) == (15, 30, "#0f766e")
    assert (row.plan_code, row.status, row.paid_until) == ("pilot", "pilot", None)
    assert (row.online_booking_enabled, row.online_auto_confirm) == (False, False)
    assert (row.booking_horizon_days, row.booking_min_notice_hours, row.booking_max_per_day, row.booking_block_no_shows) == (30, 2, 20, 2)
    assert len(row.display_token) == 32 and row.is_demo is False
    assert "{patient}" in row.reminder_template_fr and "{time}" in row.reminder_template_ar
    assert "d'empêchement" in row.reminder_template_fr


def test_practice_needs_a_specialty_and_a_valid_unique_slug(db: Engine, make_practice: Factory) -> None:
    make_practice(slug="cabinet-lac")
    ok = {"name": "X", "specialty": "generaliste"}
    assert refused(db, insert(practice).values(**ok, slug="cabinet-lac")) == "practice_slug_key"
    for slug in ("Cabinet", "ab", "-abc", "abc-", "a_b_c", "x" * 41):
        assert refused(db, insert(practice).values(**ok, slug=slug)) == "practice_slug_format", slug
    for slug in ("www", "admin", "demo", "api"):
        assert refused(db, insert(practice).values(**ok, slug=slug)) == "practice_slug_reserved", slug
    refused(db, insert(practice).values(name="X", slug="sans-specialite"))
    assert refused(db, insert(practice).values(name="X", slug="mauvaise", specialty="chirurgien")) == "practice_specialty_check"


def test_practice_value_checks(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    where = practice.c.id == p.id
    for values in (
        {"brand_color": "teal"},
        {"brand_color": "#0F766E"},
        {"governorate": "paris"},
        {"whatsapp": "20123456"},
        {"status": "frozen"},
        {"plan_code": "gold"},
        {"weekly_hours": text("'[]'::jsonb")},
        {"booking_horizon_days": 0},
        {"booking_block_no_shows": -1},
        {"is_demo": True},  # a demo needs an expiry
    ):
        refused(db, update(practice).where(where).values(**values))
    with db.begin() as conn:
        conn.execute(update(practice).where(where).values(governorate="ben_arous", whatsapp="+21620123456", status="suspended"))


def test_admin_has_no_practice_and_staff_has_one(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    base = {"password_hash": "x", "name": "n"}
    refused(db, insert(app_user).values(email="a@x.tn", role="admin", practice_id=p.id, **base))
    refused(db, insert(app_user).values(email="b@x.tn", role="owner", practice_id=None, **base))
    refused(db, insert(app_user).values(email="Upper@x.tn", role="owner", practice_id=p.id, **base))
    refused(db, insert(app_user).values(email="c@x.tn", role="boss", practice_id=p.id, **base))


def test_practitioners_and_services(db: Engine, make_practice: Factory) -> None:
    p = make_practice(practitioners=["Dr. Amira Ben Ali", "Dr. Karim Trabelsi"])
    assert [d.name for d in p.practitioners] == ["Dr. Amira Ben Ali", "Dr. Karim Trabelsi"]
    assert p.practitioners[0].online_bookable is True and p.practitioners[0].active is True
    refused(db, insert(practitioner).values(practice_id=p.id, name="X", specialty="sorcier"))
    refused(db, insert(practitioner).values(practice_id=p.id, name="X", color="red"))
    refused(db, insert(service).values(practice_id=p.id, name_fr="X", duration_min=2))
    refused(db, insert(service).values(practice_id=p.id, name_fr="X", duration_min=30, price_millimes=-1))
    refused(db, insert(practice_closure).values(practice_id=p.id, starts_on=date(2026, 8, 10), ends_on=date(2026, 8, 1)))


# --- appointments: no double booking (section 11.1) ------------------------------------------------------------------


@pytest.fixture
def booked(make_practice: Factory, make_patient: Factory, make_appointment: Factory, clock: Any) -> dict[str, Any]:
    p = make_practice(practitioners=["Dr. A", "Dr. B"])
    a, b = p.practitioners
    amira, karim = make_patient(p), make_patient(p)
    at = clock.now() + timedelta(days=1)
    first = make_appointment(amira, practitioner_id=a.id, starts_at=at, duration_min=30)
    return {"practice": p, "a": a, "b": b, "amira": amira, "karim": karim, "at": at, "first": first}


def test_the_same_practitioner_cannot_be_booked_twice(db: Engine, booked: dict[str, Any], make_appointment: Factory) -> None:
    with pytest.raises(IntegrityError) as caught:
        make_appointment(booked["karim"], practitioner_id=booked["a"].id, starts_at=booked["at"] + timedelta(minutes=15))
    assert constraint_name(caught.value) == "appointment_practitioner_no_overlap"


def test_another_practitioner_back_to_back_and_freed_slots_are_fine(booked: dict[str, Any], make_appointment: Factory) -> None:
    at, a, b = booked["at"], booked["a"], booked["b"]
    make_appointment(booked["karim"], practitioner_id=b.id, starts_at=at)  # other practitioner, same time
    make_appointment(booked["karim"], practitioner_id=a.id, starts_at=at + timedelta(minutes=30))  # right after
    make_appointment(booked["karim"], practitioner_id=a.id, starts_at=at - timedelta(minutes=30))  # right before
    gone = make_appointment(booked["karim"], practitioner_id=a.id, starts_at=at + timedelta(hours=2), status="cancelled")
    make_appointment(booked["karim"], practitioner_id=a.id, starts_at=gone.starts_at)  # cancelled does not block
    absent = make_appointment(booked["karim"], practitioner_id=a.id, starts_at=at + timedelta(hours=3), status="no_show")
    make_appointment(booked["karim"], practitioner_id=a.id, starts_at=absent.starts_at)  # no-show does not block


def test_a_patient_is_never_twice_at_the_same_time(booked: dict[str, Any], make_appointment: Factory) -> None:
    with pytest.raises(IntegrityError) as caught:
        make_appointment(booked["amira"], practitioner_id=booked["b"].id, starts_at=booked["at"] + timedelta(minutes=10))
    assert constraint_name(caught.value) == "appointment_patient_no_overlap"


def test_appointments_without_practitioner_share_one_calendar(booked: dict[str, Any], make_appointment: Factory) -> None:
    at = booked["at"] + timedelta(days=1)
    make_appointment(booked["amira"], practitioner_id=None, starts_at=at)
    with pytest.raises(IntegrityError):
        make_appointment(booked["karim"], practitioner_id=None, starts_at=at + timedelta(minutes=5))


def test_online_requests_block_the_slot(booked: dict[str, Any], make_appointment: Factory) -> None:
    at = booked["at"] + timedelta(days=2)
    make_appointment(booked["amira"], practitioner_id=booked["a"].id, starts_at=at, status="requested", source="online")
    with pytest.raises(IntegrityError):
        make_appointment(booked["karim"], practitioner_id=booked["a"].id, starts_at=at)


def test_ends_at_must_match_the_duration(db: Engine, booked: dict[str, Any]) -> None:
    pat, at = booked["karim"], booked["at"] + timedelta(days=3)
    base = {"practice_id": pat.practice_id, "patient_id": pat.id, "starts_at": at, "duration_min": 30}
    refused(db, insert(appointment).values(**base, ends_at=at))
    refused(db, insert(appointment).values(**base, ends_at=at + timedelta(minutes=20)))
    refused(db, insert(appointment).values(**base, ends_at=at + timedelta(minutes=30), source="phone"))
    refused(db, insert(appointment).values(**base, ends_at=at + timedelta(minutes=30), booking_token_hash="abc"))


# --- tenants, cascades -----------------------------------------------------------------------------------------------


def test_rows_cannot_point_to_a_patient_of_another_practice(db: Engine, make_practice: Factory, make_patient: Factory, clock: Any) -> None:
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    now = clock.now()
    for statement in [
        insert(appointment).values(practice_id=mine.id, patient_id=stranger.id, starts_at=now, ends_at=now + timedelta(minutes=30)),
        insert(treatment).values(practice_id=mine.id, patient_id=stranger.id, label="X", price_millimes=1),
        insert(payment).values(practice_id=mine.id, patient_id=stranger.id, amount_millimes=1, method="cash", paid_at=now),
        insert(queue_entry).values(practice_id=mine.id, day=now.date(), ticket_no=1, patient_id=stranger.id, arrived_at=now),
    ]:
        refused(db, statement)


def test_value_checks(db: Engine, make_practice: Factory, make_patient: Factory, clock: Any) -> None:
    p = make_practice()
    pat = make_patient(p)
    now = clock.now()
    for statement in [
        insert(patient).values(practice_id=p.id, first_name="A", last_name="B", phone="20123456"),
        insert(payment).values(practice_id=p.id, patient_id=pat.id, amount_millimes=0, method="cash", paid_at=now),
        insert(payment).values(practice_id=p.id, patient_id=pat.id, amount_millimes=5, method="bitcoin", paid_at=now),
        insert(appointment).values(practice_id=p.id, patient_id=pat.id, starts_at=now, ends_at=now + timedelta(minutes=30), status="maybe"),
        insert(appointment).values(practice_id=p.id, patient_id=pat.id, starts_at=now, ends_at=now + timedelta(minutes=30), deposit_required_millimes=-1),
        insert(treatment).values(practice_id=p.id, patient_id=pat.id, label="X", price_millimes=-1),
        insert(queue_entry).values(practice_id=p.id, day=now.date(), ticket_no=1, status="gone", arrived_at=now),
        insert(invitation).values(practice_id=p.id, role="admin", token_hash="a" * 64, expires_at=now),
        insert(invitation).values(practice_id=p.id, role="owner", token_hash="not-a-hash", expires_at=now),
    ]:
        refused(db, statement)


def test_invoices(db: Engine, make_practice: Factory, clock: Any) -> None:
    p = make_practice()
    base = {"practice_id": p.id, "plan_code": "cabinet_mensuel", "period_start": date(2026, 11, 1),
            "period_end": date(2026, 11, 30), "amount_millimes": 49_000, "due_on": date(2026, 11, 1)}
    with db.begin() as conn:
        conn.execute(insert(invoice).values(**base, number="DAF-2026-0001"))
    assert refused(db, insert(invoice).values(**base, number="DAF-2026-0001")) == "invoice_number_key"
    refused(db, insert(invoice).values(**base, number="2026-1"))
    refused(db, insert(invoice).values(**base, number="DAF-2026-0002", status="lost"))
    refused(db, insert(invoice).values(**base, number="DAF-2026-0003", status="paid"))  # paid needs paid_at
    refused(db, insert(invoice).values(**base, number="DAF-2026-0004", method="bitcoin"))
    refused(db, insert(invoice).values(**{**base, "period_end": date(2026, 10, 1)}, number="DAF-2026-0005"))
    with db.begin() as conn:
        conn.execute(insert(invoice).values(**base, number="DAF-2026-0006", status="paid", paid_at=clock.now(), method="virement"))


def test_one_ticket_number_per_practice_and_day(make_practice: Factory, make_queue_entry: Factory) -> None:
    p, q = make_practice(), make_practice()
    make_queue_entry(p, 1)
    make_queue_entry(q, 1)  # another practice may use the same number
    with pytest.raises(IntegrityError):
        make_queue_entry(p, 1)


def test_deleting_a_practice_deletes_everything_of_it(
    db: Engine, clock: Any, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_queue_entry: Factory, make_treatment: Factory, make_payment: Factory, make_invitation: Factory,
    make_service: Factory,
) -> None:
    doomed, kept = make_practice(practitioners=["Dr. X"]), make_practice(practitioners=["Dr. Y"])
    for p in (doomed, kept):
        user = make_user(p, "assistant")
        pat = make_patient(p)
        svc = make_service(p)
        appt = make_appointment(pat, practitioner_id=p.practitioners[0].id, service_id=svc.id)
        make_queue_entry(p, 1, patient_id=pat.id, appointment_id=appt.id, name="X")
        make_treatment(pat, 30_000, appointment_id=appt.id)
        make_payment(pat, 10_000, appointment_id=appt.id, received_by=user.id)
        make_invitation(p, "assistant", created_by=user.id)
        with db.begin() as conn:
            conn.execute(insert(practice_closure).values(practice_id=p.id, starts_on=date(2026, 12, 24), ends_on=date(2026, 12, 26)))
            conn.execute(insert(invoice).values(practice_id=p.id, number=f"DAF-2026-{p.id:04d}", plan_code="pilot",
                                                period_start=date(2026, 11, 1), period_end=date(2026, 11, 30),
                                                amount_millimes=0, due_on=date(2026, 11, 1)))
            conn.execute(insert(import_job).values(practice_id=p.id, created_by=user.id, filename="patients.xlsx",
                                                   file_bytes=b"PK", expires_at=clock.now() + timedelta(hours=24)))
            conn.execute(insert(import_template).values(practice_id=p.id, name="Mon Excel", kind="patients",
                                                        mapping={"lastName": 0, "phone": 2}))
            conn.execute(insert(feedback).values(practice_id=p.id, user_id=user.id, message="Super", page="/app"))
            conn.execute(insert(cash_closing).values(practice_id=p.id, day=date(2026, 10, 29), expected_cash_millimes=0,
                                                     counted_cash_millimes=0, closed_by=user.id, closed_at=clock.now()))
            sup = conn.execute(insert(supplier).values(practice_id=p.id, name="Dentalia").returning(supplier.c.id)).scalar_one()
            product = conn.execute(insert(stock_product).values(practice_id=p.id, name="Gants", supplier_id=sup)
                                   .returning(stock_product.c.id)).scalar_one()
            receipt = conn.execute(insert(stock_receipt).values(practice_id=p.id, received_on=date(2026, 10, 29), supplier_id=sup,
                                                                created_by=user.id).returning(stock_receipt.c.id)).scalar_one()
            line = conn.execute(insert(stock_receipt_line).values(practice_id=p.id, receipt_id=receipt, product_id=product,
                                                                  quantity=5).returning(stock_receipt_line.c.id)).scalar_one()
            conn.execute(insert(stock_movement).values(practice_id=p.id, product_id=product, kind="receipt", quantity=5,
                                                       receipt_line_id=line, created_by=user.id))
            conn.execute(insert(audit_log).values(practice_id=p.id, user_id=user.id, entity="stock_movement", entity_id=1,
                                                  action="delete"))
            gear = conn.execute(insert(equipment).values(practice_id=p.id, name="Autoclave", kind="autoclave")
                                .returning(equipment.c.id)).scalar_one()
            task = conn.execute(insert(hygiene_task).values(practice_id=p.id, title="Bowie-Dick", equipment_id=gear,
                                                            frequency="weekly", weekday=1, starts_on=date(2026, 10, 26))
                                .returning(hygiene_task.c.id)).scalar_one()
            conn.execute(insert(hygiene_task_done).values(practice_id=p.id, task_id=task, due_on=date(2026, 10, 26),
                                                          done_by=user.id, done_at=clock.now()))
            conn.execute(insert(hygiene_task_due).values(practice_id=p.id, task_id=task, due_on=date(2026, 10, 26),
                                                         title="Bowie-Dick", equipment_id=gear, equipment_name="Autoclave",
                                                         status="done"))
            cycle = conn.execute(insert(sterilization_cycle).values(
                practice_id=p.id, equipment_id=gear, number=1, run_at=clock.now(), result="ok", pack_count=1,
                performed_by=user.id, performed_by_name="X", initials="X", created_at=clock.now(),
            ).returning(sterilization_cycle.c.id)).scalar_one()
            pack = conn.execute(insert(sterile_pack).values(
                practice_id=p.id, cycle_id=cycle, seq=1, code="A1-0001-01", content="Kit", packaging="sachet",
                expires_on=date(2027, 1, 28)).returning(sterile_pack.c.id)).scalar_one()
            conn.execute(insert(sterile_pack_use).values(practice_id=p.id, pack_id=pack, patient_id=pat.id,
                                                         patient_no=pat.id, appointment_id=appt.id, used_at=clock.now(),
                                                         used_by=user.id, used_by_name="X"))
            conn.execute(insert(specimen_label_log).values(
                practice_id=p.id, patient_id=pat.id, appointment_id=appt.id, items=[{"kind": "edta", "count": 1}],
                label_count=1, collected_at=clock.now(), printed_by=user.id, printed_by_name="X", printed_at=clock.now()))
    with db.begin() as conn:
        conn.execute(delete(practice).where(practice.c.id == doomed.id))
        for table in ALL_TABLES:
            if "practice_id" in table.c:
                count = lambda pid: conn.execute(select(func.count()).select_from(table).where(table.c.practice_id == pid)).scalar_one()  # noqa: E731
                assert count(doomed.id) == 0, table.name
                assert count(kept.id) == 1, table.name
        assert conn.execute(select(func.count()).select_from(plan)).scalar_one() == 3


def test_deleting_a_patient_deletes_their_rows_and_keeps_others(
    db: Engine, make_practice: Factory, make_patient: Factory, make_appointment: Factory, make_queue_entry: Factory,
    make_treatment: Factory, make_payment: Factory, clock: Any,
) -> None:
    p = make_practice()
    gone, stays = make_patient(p), make_patient(p)
    for n, pat in enumerate((gone, stays), start=1):
        make_appointment(pat, starts_at=clock.now() + timedelta(hours=n))
        make_queue_entry(p, n, patient_id=pat.id)
        make_treatment(pat, 1000)
        make_payment(pat, 1000)
    with db.begin() as conn:
        conn.execute(delete(patient).where(patient.c.id == gone.id))
        for table in (appointment, queue_entry, treatment, payment):
            assert conn.execute(select(table.c.patient_id)).scalars().all() == [stays.id], table.name


def test_deleting_practitioners_services_users_or_appointments_keeps_the_rest(
    db: Engine, make_practice: Factory, make_user: Factory, make_patient: Factory, make_appointment: Factory,
    make_queue_entry: Factory, make_payment: Factory, make_service: Factory, clock: Any,
) -> None:
    p = make_practice(practitioners=["Dr. Z"])
    doctor = p.practitioners[0]
    assistant = make_user(p, "assistant")
    svc = make_service(p)
    pat = make_patient(p)
    appt = make_appointment(pat, practitioner_id=doctor.id, created_by=assistant.id, service_id=svc.id)
    entry = make_queue_entry(p, 1, appointment_id=appt.id)
    pay = make_payment(pat, 5000, appointment_id=appt.id, received_by=assistant.id)
    with db.begin() as conn:
        conn.execute(delete(practitioner).where(practitioner.c.id == doctor.id))
        conn.execute(delete(service).where(service.c.id == svc.id))
        conn.execute(delete(app_user).where(app_user.c.id == assistant.id))
        row = conn.execute(select(appointment.c.practitioner_id, appointment.c.service_id, appointment.c.created_by)).one()
        assert tuple(row) == (None, None, None)
        assert conn.execute(select(payment.c.received_by).where(payment.c.id == pay.id)).scalar_one() is None
        conn.execute(delete(appointment).where(appointment.c.id == appt.id))
        assert conn.execute(select(queue_entry.c.appointment_id).where(queue_entry.c.id == entry.id)).scalar_one() is None
        assert conn.execute(select(payment.c.appointment_id).where(payment.c.id == pay.id)).scalar_one() is None


# --- import, password reset, feedback, alerts, series (section 14 and backlog) ------------------------------------------


def test_import_jobs_and_templates(db: Engine, make_practice: Factory, make_user: Factory, clock: Any) -> None:
    p = make_practice()
    owner = make_user(p)
    with db.begin() as conn:
        job = conn.execute(
            insert(import_job).values(practice_id=p.id, created_by=owner.id, filename="patients.csv", file_bytes=b"a;b\n1;2",
                                      expires_at=clock.now() + timedelta(hours=24)).returning(import_job)
        ).one()
        tpl = conn.execute(
            insert(import_template).values(practice_id=p.id, name="Excel", kind="appointments", mapping={"date": 0})
            .returning(import_template)
        ).one()
    assert len(str(job.id)) == 36 and job.committed_at is None and bytes(job.file_bytes) == b"a;b\n1;2"
    assert (tpl.mapping, tpl.options) == ({"date": 0}, {})
    refused(db, insert(import_template).values(practice_id=p.id, name="X", kind="invoices", mapping={}))
    with db.begin() as conn:
        conn.execute(delete(app_user).where(app_user.c.id == owner.id))
        assert conn.execute(select(import_job.c.created_by)).scalar_one() is None


def test_password_resets_belong_to_a_user(db: Engine, make_user: Factory, clock: Any) -> None:
    user, admin = make_user(), make_user(role="admin")
    base = {"user_id": user.id, "created_by": admin.id, "expires_at": clock.now() + timedelta(hours=1)}
    with db.begin() as conn:
        conn.execute(insert(password_reset).values(**base, token_hash="a" * 64))
    assert refused(db, insert(password_reset).values(**base, token_hash="a" * 64)) == "password_reset_token_hash_key"
    refused(db, insert(password_reset).values(**base, token_hash="clear-token"))
    with db.begin() as conn:
        conn.execute(delete(app_user).where(app_user.c.id == user.id))
        assert conn.execute(select(func.count()).select_from(password_reset)).scalar_one() == 0


def test_feedback(db: Engine, make_practice: Factory, make_user: Factory) -> None:
    p = make_practice()
    user = make_user(p)
    with db.begin() as conn:
        conn.execute(insert(feedback).values(practice_id=p.id, user_id=user.id, message="Une idée", page="/app/agenda"))
    refused(db, insert(feedback).values(practice_id=p.id, user_id=user.id, message="", page="/app"))
    with db.begin() as conn:
        conn.execute(delete(app_user).where(app_user.c.id == user.id))
        assert conn.execute(select(feedback.c.user_id, feedback.c.message)).one() == (None, "Une idée")


def test_patient_alerts_and_appointment_series(make_practice: Factory, make_patient: Factory, make_appointment: Factory, clock: Any) -> None:
    import uuid

    p = make_practice()
    pat = make_patient(p, alerts="Allergie pénicilline")
    assert pat.alerts == "Allergie pénicilline"
    assert make_patient(p).alerts == ""
    series = uuid.uuid4()
    first = make_appointment(pat, series_id=series)
    second = make_appointment(pat, series_id=series, starts_at=first.starts_at + timedelta(days=7))
    assert first.series_id == second.series_id == series
    assert make_appointment(pat, starts_at=first.starts_at + timedelta(days=1)).series_id is None


def test_onboarding_state_and_alert_length(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    p = make_practice()
    assert p.onboarding == {}
    with db.begin() as conn:
        conn.execute(update(practice).where(practice.c.id == p.id).values(onboarding={"dismissed": True, "done": ["install"]}))
    make_patient(p, alerts="x" * 500)
    refused(db, insert(patient).values(practice_id=p.id, first_name="A", last_name="B", phone="+21620123456", alerts="x" * 501))
    refused(db, update(practice).where(practice.c.id == p.id).values(onboarding=text("'[]'::jsonb")))
