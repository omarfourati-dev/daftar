"""Migration 0012 (sterilisation cycles, packs, their use, specimen labels, birth dates): constraints that keep the
traceability believable and the tenants apart."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, delete, insert, select, update
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
        practice_id=mine.id, pack_id=pack.id, patient_id=patient_other.id, used_at=AT, used_by_name="X"
    )) == "sterile_pack_use_patient_fkey"
    _one(db, sterile_pack_use, practice_id=mine.id, pack_id=pack.id, patient_id=patient_mine.id, used_at=AT, used_by_name="X")
    assert refused(db, insert(sterile_pack_use).values(
        practice_id=mine.id, pack_id=pack.id, patient_id=patient_mine.id, used_at=AT, used_by_name="Y"
    )) == "sterile_pack_use_once"
    # a used pack keeps its cycle; deleting the patient (GDPR) removes the use, never the cycle
    assert refused(db, delete(sterilization_cycle).where(sterilization_cycle.c.id == cycle.id)) == "sterile_pack_use_pack_fkey"
    with db.begin() as conn:
        conn.execute(delete(patient).where(patient.c.id == patient_mine.id))
        assert conn.execute(select(sterile_pack_use)).all() == []
        conn.execute(delete(sterilization_cycle).where(sterilization_cycle.c.id == cycle.id))
        assert conn.execute(select(sterile_pack).where(sterile_pack.c.cycle_id == cycle.id)).all() == []
        # the whole practice can still go
        conn.execute(delete(practice).where(practice.c.id == other.id))


def test_specimen_prints_belong_to_a_patient_of_the_practice(db: Engine, make_practice: Factory, make_patient: Factory) -> None:
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    values = {"items": [{"kind": "edta", "count": 2}], "label_count": 2, "collected_at": AT, "printed_by_name": "N",
              "printed_at": AT}
    assert refused(db, insert(specimen_label_log).values(practice_id=mine.id, patient_id=stranger.id, **values)) == (
        "specimen_label_log_patient_fkey")
    refused(db, insert(specimen_label_log).values(practice_id=mine.id, patient_id=make_patient(mine).id,
                                                  **{**values, "label_count": 0}))


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
