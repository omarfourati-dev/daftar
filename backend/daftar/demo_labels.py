"""Sterilisation, traceability and specimen labels of a demo practice (spec stock-hygiène 8), so that the "Stérilisation"
tab, the label preview and the traceability show something from the first click.

- Practices with an autoclave in their hygiene plan (dentists): the autoclave ``A1`` ran five cycles – one 100 days
  ago (its packs are expired now), one five opening days ago, a "non conforme" one three opening days ago (no labels,
  run again the same afternoon) and one this morning. The packs of the last week went to the patients of the done
  appointments, one each, so both searches of the traceability find something.
- Practices that take specimens (not dentists, physiotherapists, psychologists): three prints of specimen labels for
  done appointments of the last days.
- Every second demo patient has a full birth date (its year is the patient's year).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Connection, insert, select, update

from .clock import TUNIS, at_tunis
from .hours import DEFAULT_WEEKLY_HOURS, windows_for
from .label_rules import DEFAULT_SHELF_LIFE_DAYS, initials, pack_code, pack_contents, sterile_until
from .tables import (
    equipment,
    patient,
    practice,
    specimen_label_log,
    sterile_pack,
    sterile_pack_use,
    sterilization_cycle,
)

NO_SPECIMENS = ("dentiste", "kinesitherapeute", "psychologue")
SPECIMENS: dict[str, list[list[tuple[str, int]]]] = {
    "pediatre": [[("edta", 1)], [("urine", 1)], [("selles", 1)]],
    "gynecologue": [[("frottis", 1)], [("sec", 1), ("edta", 1)], [("urine", 1)]],
}
DEFAULT_SPECIMENS = [[("edta", 1), ("sec", 1)], [("urine", 1)], [("edta", 1), ("citrate", 1)]]
NOT_OK_NOTE = ("Indicateur non viré – charge restérilisée l’après-midi", "المؤشر لم يتغيّر – أُعيد تعقيم الحمولة بعد الظهر")


def _open(day: date) -> bool:
    return bool(windows_for(DEFAULT_WEEKLY_HOURS, day))


def _birth_dates(conn: Connection, practice_id: int, rng: random.Random) -> None:
    rows = conn.execute(select(patient.c.id, patient.c.birth_year).where(patient.c.practice_id == practice_id)
                        .order_by(patient.c.id)).all()
    for n, row in enumerate(rows):
        if n % 2 == 0 and row.birth_year:
            born = date(row.birth_year, rng.randint(1, 12), rng.randint(1, 28))
            conn.execute(update(patient).where(patient.c.id == row.id).values(birth_date=born))


def _sterilisation(
    conn: Connection, *, practice_id: int, user_id: int, user_name: str, specialty: str, arabic: bool, now: datetime,
    plans: Sequence[Any], patient_ids: Sequence[int],
) -> None:
    gear = conn.execute(select(equipment.c.id).where(equipment.c.practice_id == practice_id, equipment.c.kind == "autoclave")
                        .order_by(equipment.c.id).limit(1)).scalar_one_or_none()
    if gear is None:
        return
    conn.execute(update(equipment).where(equipment.c.id == gear).values(label_code="A1", last_cycle_number=412))
    conn.execute(update(practice).where(practice.c.id == practice_id).values(autoclave_codes_given=1))
    today = now.astimezone(TUNIS).date()
    before = [today - timedelta(days=n) for n in range(1, 30) if _open(today - timedelta(days=n))]
    contents = pack_contents(specialty, "ar" if arabic else "fr")
    examen, extraction, other = contents[0], contents[1], contents[2]
    # (number, when, result, packs [(content, packaging, quantity)], load of a failed cycle, note)
    runs: list[tuple[int, datetime, str, list[tuple[str, str, int]], int, str]] = [
        (380, at_tunis(today - timedelta(days=100), time(8, 0)), "ok", [(examen, "sachet", 2)], 0, ""),
        (409, at_tunis(before[4], time(7, 50)), "ok", [(examen, "sachet", 4), (extraction, "sachet", 2)], 0, ""),
        (410, at_tunis(before[2], time(12, 40)), "not_ok", [], 5, NOT_OK_NOTE[1 if arabic else 0]),
        (411, at_tunis(before[2], time(13, 30)), "ok", [(examen, "sachet", 3), (other, "double_sachet", 2)], 0, ""),
        (412, min(at_tunis(today, time(7, 45)), now - timedelta(minutes=10)), "ok",
         [(examen, "sachet", 5), (other, "sachet", 2), (extraction, "double_sachet", 1)], 0, ""),
    ]
    packs: list[dict[str, Any]] = []
    for number, run_at, result, lines, load, note in runs:
        cycle_id = conn.execute(insert(sterilization_cycle).values(
            practice_id=practice_id, equipment_id=gear, number=number, run_at=run_at, program="134 °C – 18 min",
            result=result, pack_count=sum(q for _, _, q in lines) or load, note=note, performed_by=user_id,
            performed_by_name=user_name, initials=initials(user_name), recorded_by=user_id, recorded_by_name=user_name,
            created_at=run_at,
        ).returning(sterilization_cycle.c.id)).scalar_one()
        seq = 0
        for content, packaging, quantity in lines:
            for _ in range(quantity):
                seq += 1
                pack_id = conn.execute(insert(sterile_pack).values(
                    practice_id=practice_id, cycle_id=cycle_id, seq=seq, code=pack_code("A1", number, seq),
                    content=content, packaging=packaging,
                    expires_on=sterile_until(run_at.astimezone(TUNIS).date(), DEFAULT_SHELF_LIFE_DAYS),
                ).returning(sterile_pack.c.id)).scalar_one()
                packs.append({"id": pack_id, "run_at": run_at, "content": content, "used": False})
    done = sorted((p for p in plans if p.status == "done" and p.end <= now and p.start >= now - timedelta(days=7)),
                  key=lambda p: p.start)
    uses = []
    for plan in done[-8:]:
        ready = [k for k in packs if not k["used"] and k["run_at"] < plan.start and k["content"] == examen
                 and k["run_at"] >= plan.start - timedelta(days=30)]
        if not ready:
            continue
        pick = max(ready, key=lambda k: k["run_at"])
        pick["used"] = True
        uses.append({"practice_id": practice_id, "pack_id": pick["id"], "patient_id": patient_ids[plan.patient],
                     "patient_no": patient_ids[plan.patient], "appointment_id": plan.id,
                     "used_at": plan.start + timedelta(minutes=5), "used_by": user_id, "used_by_name": user_name})
    if uses:
        conn.execute(insert(sterile_pack_use), uses)


def _specimens(
    conn: Connection, *, practice_id: int, user_id: int, user_name: str, specialty: str, now: datetime,
    plans: Sequence[Any], patient_ids: Sequence[int],
) -> None:
    if specialty in NO_SPECIMENS:
        return
    done = sorted((p for p in plans if p.status == "done" and p.end <= now and p.start < now - timedelta(hours=12)),
                  key=lambda p: p.start)
    rows = []
    for plan, kinds in zip(done[-3:], SPECIMENS.get(specialty, DEFAULT_SPECIMENS), strict=False):
        items = [{"kind": kind, "count": count, "label": ""} for kind, count in kinds]
        at = plan.start + timedelta(minutes=10)
        rows.append({"practice_id": practice_id, "patient_id": patient_ids[plan.patient], "appointment_id": plan.id,
                     "items": items, "label_count": sum(count for _, count in kinds), "collected_at": at,
                     "collected_by": user_name, "printed_by": user_id, "printed_by_name": user_name, "printed_at": at})
    if rows:
        conn.execute(insert(specimen_label_log), rows)


def seed_labels(
    conn: Connection, *, practice_id: int, user_id: int, user_name: str, specialty: str, arabic: bool, now: datetime,
    plans: Sequence[Any], patient_ids: Sequence[int], rng: random.Random,
) -> None:
    _birth_dates(conn, practice_id, rng)
    _sterilisation(conn, practice_id=practice_id, user_id=user_id, user_name=user_name, specialty=specialty,
                   arabic=arabic, now=now, plans=plans, patient_ids=patient_ids)
    _specimens(conn, practice_id=practice_id, user_id=user_id, user_name=user_name, specialty=specialty, now=now,
               plans=plans, patient_ids=patient_ids)
