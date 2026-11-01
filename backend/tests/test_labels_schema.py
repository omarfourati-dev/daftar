"""Migrations 0012 and 0013 (sterilisation cycles, packs, their use, specimen labels, birth dates; codes never given
twice, cancelled cycles, a use that outlives its patient): constraints that keep the traceability believable and the
tenants apart."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from daftar.db import constraint_name
from daftar.tables import (
    equipment,
    patient,
    practice,
    specimen_label_log,
    sterile_pack,
    sterile_pack_use,
    sterilization_cycle,
)
from tests.conftest import _alembic

Factory = Callable[..., Any]
AT = datetime(2026, 10, 30, 8, tzinfo=UTC)


def refused(db: Engine, statement: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, db.begin() as conn:
        conn.execute(statement)
    return constraint_name(caught.value)


def _one(db: Engine, table: Any, **values: Any) -> Any:
    with db.begin() as conn:
        return conn.execute(insert(table).values(**values).returning(table)).one()


def _cycle(db: Engine, practice_id: int, equipment_id: int, number: int = 412, **values: Any) -> Any:
    return _one(db, sterilization_cycle, practice_id=practice_id, equipment_id=equipment_id, number=number, run_at=AT,
                result="ok", pack_count=1, performed_by_name="Nisrine", initials="N", created_at=AT, **values)


def _pack(db: Engine, practice_id: int, cycle_id: int, seq: int = 1, **values: Any) -> Any:
    return _one(db, sterile_pack, practice_id=practice_id, cycle_id=cycle_id, seq=seq, code=f"A1-0412-{seq:02d}",
                content="Kit examen", packaging="sachet", expires_on=date(2027, 1, 28), **values)


def test_a_birth_date_and_its_year_never_disagree(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    p = make_practice()
    born = make_patient(p, birth_year=1978)
    assert born.birth_date is None  # existing patients keep their year alone
    with db.begin() as conn:
        conn.execute(update(patient).where(patient.c.id == born.id).values(birth_date=date(1978, 3, 12)))
    assert refused(db, update(patient).where(patient.c.id == born.id).values(birth_year=1979)) == "patient_birth_date_year_check"
    assert refused(db, update(patient).where(patient.c.id == born.id).values(birth_year=None)) == "patient_birth_date_year_check"


def test_settings_start_empty(db: Engine, make_practice: Factory) -> None:
    assert make_practice().label_settings == {}


def test_autoclave_codes_and_cycle_numbers_are_unique(db: Engine, make_practice: Factory) -> None:
    p, other = make_practice(), make_practice()
    autoclave = _one(db, equipment, practice_id=p.id, name="Autoclave", kind="autoclave", label_code="A1")
    _one(db, equipment, practice_id=other.id, name="Autoclave", kind="autoclave", label_code="A1")
    assert refused(db, insert(equipment).values(practice_id=p.id, name="Autre", label_code="A1")) == "equipment_label_code_key"
    refused(db, insert(equipment).values(practice_id=p.id, name="Mauvais", label_code="a-1"))
    _cycle(db, p.id, autoclave.id)
    assert refused(db, insert(sterilization_cycle).values(
        practice_id=p.id, equipment_id=autoclave.id, number=412, run_at=AT, result="ok", pack_count=0,
        performed_by_name="X", initials="X", created_at=AT)) == "sterilization_cycle_number_key"
    for values in ({"result": "maybe"}, {"number": 0}, {"pack_count": 100}, {"program": "x" * 61}):
        refused(db, insert(sterilization_cycle).values(**{
            "practice_id": p.id, "equipment_id": autoclave.id, "number": 999, "run_at": AT, "result": "ok", "pack_count": 1,
            "performed_by_name": "X", "initials": "X", "created_at": AT, **values}))


def test_cycles_packs_and_uses_stay_in_their_practice(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    mine, other = make_practice(), make_practice()
    autoclave = _one(db, equipment, practice_id=mine.id, name="Autoclave", kind="autoclave", label_code="A1")
    foreign = _one(db, equipment, practice_id=other.id, name="Autoclave", kind="autoclave", label_code="A1")
    assert refused(db, insert(sterilization_cycle).values(
        practice_id=mine.id, equipment_id=foreign.id, number=1, run_at=AT, result="ok", pack_count=0,
        performed_by_name="X", initials="X", created_at=AT)) == "sterilization_cycle_equipment_fkey"
    cycle = _cycle(db, mine.id, autoclave.id)
    foreign_cycle = _cycle(db, other.id, foreign.id)
    assert refused(db, insert(sterile_pack).values(
        practice_id=mine.id, cycle_id=foreign_cycle.id, seq=1, code="A1-0412-01", content="Kit", packaging="sachet",
        expires_on=date(2027, 1, 1))) == "sterile_pack_cycle_fkey"
    pack = _pack(db, mine.id, cycle.id)
    assert refused(db, insert(sterile_pack).values(
        practice_id=mine.id, cycle_id=cycle.id, seq=2, code="A1-0412-01", content="Kit", packaging="sachet",
        expires_on=date(2027, 1, 1))) == "sterile_pack_code_key"
    assert refused(db, insert(sterile_pack).values(
        practice_id=mine.id, cycle_id=cycle.id, seq=1, code="A1-0412-99", content="Kit", packaging="sachet",
        expires_on=date(2027, 1, 1))) == "sterile_pack_seq_key"
    refused(db, insert(sterile_pack).values(practice_id=mine.id, cycle_id=cycle.id, seq=3, code="A1-0412-03",
                                            content="Kit", packaging="boite", expires_on=date(2027, 1, 1)))
    patient_mine, patient_other = make_patient(mine), make_patient(other)
    assert refused(db, insert(sterile_pack_use).values(
        practice_id=mine.id, pack_id=pack.id, patient_id=patient_other.id, patient_no=patient_other.id, used_at=AT,
        used_by_name="X"
    )) == "sterile_pack_use_patient_fkey"
    assert refused(db, insert(sterile_pack_use).values(
        practice_id=mine.id, pack_id=pack.id, patient_id=patient_mine.id, patient_no=patient_other.id, used_at=AT,
        used_by_name="X"
    )) == "sterile_pack_use_patient_no_check"
    _one(db, sterile_pack_use, practice_id=mine.id, pack_id=pack.id, patient_id=patient_mine.id, patient_no=patient_mine.id,
         used_at=AT, used_by_name="X")
    assert refused(db, insert(sterile_pack_use).values(
        practice_id=mine.id, pack_id=pack.id, patient_id=patient_mine.id, patient_no=patient_mine.id, used_at=AT,
        used_by_name="Y"
    )) == "sterile_pack_use_once"
    # a cycle keeps its packs (their codes are printed) and a used pack its use
    assert refused(db, delete(sterilization_cycle).where(sterilization_cycle.c.id == cycle.id)) == "sterile_pack_cycle_fkey"
    assert refused(db, delete(sterile_pack).where(sterile_pack.c.id == pack.id)) == "sterile_pack_use_pack_fkey"
    # erasing the patient (GDPR) keeps the use with the patient's number only – the app lets go of the patient first
    assert refused(db, delete(patient).where(patient.c.id == patient_mine.id)) == "sterile_pack_use_patient_fkey"
    with db.begin() as conn:
        conn.execute(update(sterile_pack_use).where(sterile_pack_use.c.patient_id == patient_mine.id).values(patient_id=None))
        conn.execute(delete(patient).where(patient.c.id == patient_mine.id))
        assert tuple(conn.execute(select(sterile_pack_use.c.patient_id, sterile_pack_use.c.patient_no)).one()) == (
            None, patient_mine.id)
        # the whole practice can still go
        conn.execute(delete(practice).where(practice.c.id == other.id))
        conn.execute(delete(practice).where(practice.c.id == mine.id))
        assert conn.execute(select(sterile_pack_use)).all() == []


def test_specimen_prints_belong_to_a_patient_of_the_practice(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    values = {"items": [{"kind": "edta", "count": 2}], "label_count": 2, "collected_at": AT, "printed_by_name": "N",
              "printed_at": AT}
    assert refused(db, insert(specimen_label_log).values(practice_id=mine.id, patient_id=stranger.id, **values)) == (
        "specimen_label_log_patient_fkey")
    refused(db, insert(specimen_label_log).values(practice_id=mine.id, patient_id=make_patient(mine).id,
                                                  **{**values, "label_count": 0}))


def test_a_cancelled_cycle_says_by_whom_when_and_why(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    autoclave = _one(db, equipment, practice_id=p.id, name="Autoclave", kind="autoclave", label_code="A1")
    cycle = _cycle(db, p.id, autoclave.id)
    assert (cycle.cancelled_at, cycle.cancel_reason, cycle.recorded_by_name) == (None, None, "")
    for values in ({"cancelled_at": AT}, {"cancelled_at": AT, "cancel_reason": "Doublon"},
                   {"cancel_reason": "Doublon", "cancelled_by_name": "Fadoua"},
                   {"cancelled_at": AT, "cancel_reason": "", "cancelled_by_name": "Fadoua"}):
        refused(db, update(sterilization_cycle).where(sterilization_cycle.c.id == cycle.id).values(**values))
    with db.begin() as conn:
        conn.execute(update(sterilization_cycle).where(sterilization_cycle.c.id == cycle.id).values(
            cancelled_at=AT, cancel_reason="Saisi deux fois", cancelled_by_name="Fadoua"))
    refused(db, update(equipment).where(equipment.c.id == autoclave.id).values(last_cycle_number=-1))
    refused(db, update(practice).where(practice.c.id == p.id).values(autoclave_codes_given=100))


def test_0013_keeps_every_number_and_starts_the_counters_at_the_highest_given(
    db: Engine, make_practice: Factory, make_patient: Factory, make_user: Factory,
) -> None:
    p, other = make_practice(), make_practice()
    owner = make_user(p, "owner", name="Dr. Fadoua")
    sami = make_patient(p)
    try:
        with db.begin() as conn:
            command.downgrade(_alembic(conn), "0012")
            gear = conn.execute(text(
                "INSERT INTO equipment (practice_id, name, kind, label_code, serial_number, note, active, created_at) "
                "VALUES (:p, 'Autoclave 1', 'autoclave', 'A1', '', '', true, now()), "
                "(:p, 'Autoclave 3', 'autoclave', 'A3', '', '', true, now()), "
                "(:p, 'Neuf', 'autoclave', NULL, '', '', true, now()) RETURNING id"), {"p": p.id}).scalars().all()
            cycles = conn.execute(text(
                "INSERT INTO sterilization_cycle (practice_id, equipment_id, number, run_at, result, pack_count, "
                "performed_by, performed_by_name, initials, created_at) VALUES "
                "(:p, :a1, 412, now(), 'ok', 1, :u, 'Dr. Fadoua', 'F', now()), "
                "(:p, :a1, 7, now(), 'ok', 0, :u, 'Dr. Fadoua', 'F', now()), "
                "(:p, :a3, 2, now(), 'ok', 0, NULL, 'Nisrine', 'N', now()) RETURNING id"),
                {"p": p.id, "a1": gear[0], "a3": gear[1], "u": owner.id}).scalars().all()
            pack = conn.execute(text(
                "INSERT INTO sterile_pack (practice_id, cycle_id, seq, code, content, packaging, expires_on) "
                "VALUES (:p, :c, 1, 'A1-0412-01', 'Kit', 'sachet', '2027-01-28') RETURNING id"),
                {"p": p.id, "c": cycles[0]}).scalar_one()
            conn.execute(text(
                "INSERT INTO sterile_pack_use (practice_id, pack_id, patient_id, used_at, used_by_name) "
                "VALUES (:p, :pack, :patient, now(), 'Nisrine')"), {"p": p.id, "pack": pack, "patient": sami.id})
            # A3's cycle n° 5 was deleted under 0012: the change log still names it
            conn.execute(text(
                "INSERT INTO audit_log (practice_id, user_name, at, entity, entity_id, action, before, reason) "
                "VALUES (:p, 'Dr. Fadoua', now(), 'sterilization_cycle', 99, 'delete', "
                "jsonb_build_object('cycle', 'A3 n° 5'), 'Doublon')"), {"p": p.id})
            command.upgrade(_alembic(conn), "head")
        with db.connect() as conn:
            counters = conn.execute(select(equipment.c.label_code, equipment.c.last_cycle_number)
                                    .where(equipment.c.practice_id == p.id).order_by(equipment.c.id)).all()
            assert [tuple(r) for r in counters] == [("A1", 412), ("A3", 5), (None, 0)]
            given = conn.execute(select(practice.c.id, practice.c.autoclave_codes_given)
                                 .where(practice.c.id.in_([p.id, other.id])).order_by(practice.c.id)).all()
            assert [tuple(r) for r in given] == [(p.id, 3), (other.id, 0)]
            numbers = conn.execute(select(sterilization_cycle.c.number).order_by(sterilization_cycle.c.id)).scalars().all()
            assert numbers == [412, 7, 2]
            recorded = conn.execute(select(sterilization_cycle.c.recorded_by, sterilization_cycle.c.recorded_by_name)
                                    .order_by(sterilization_cycle.c.id)).all()
            assert [tuple(r) for r in recorded] == [(owner.id, "Dr. Fadoua"), (owner.id, "Dr. Fadoua"), (None, "Nisrine")]
            assert tuple(conn.execute(select(sterile_pack_use.c.patient_id, sterile_pack_use.c.patient_no)).one()) == (
                sami.id, sami.id)
    finally:
        with db.begin() as conn:
            command.upgrade(_alembic(conn), "head")


def test_0012_goes_down_and_up_again(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    p = make_practice()
    make_patient(p, birth_year=1990)
    try:
        with db.begin() as conn:
            command.downgrade(_alembic(conn), "0011")
            command.upgrade(_alembic(conn), "head")
        with db.connect() as conn:
            assert conn.execute(select(patient.c.birth_year, patient.c.birth_date)).one() == (1990, None)
    finally:
        with db.begin() as conn:
            command.upgrade(_alembic(conn), "head")
