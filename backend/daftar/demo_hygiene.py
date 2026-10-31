"""Hygiene of a demo practice (spec stock-hygiène 8): the start plan of the specialty with three weeks of proofs, so
"Hygiène du jour" and the history show something from the first click.

- daily and weekly tasks started three weeks ago; nearly every past occurrence is ticked by the demo owner, one daily
  purge two opening days ago was forgotten (the history shows the gap) and one weekly autoclave test came out
  "non conforme" with its note;
- one rare task (yearly, else monthly) was due three days ago and is still open – red on top of today's list;
  other monthly tasks were done two weeks ago, yearly ones are due in a month;
- today: every second task is already ticked when the demo starts after 8:30, the rest waits.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import Connection, insert

from .clock import TUNIS, at_tunis
from .hours import DEFAULT_WEEKLY_HOURS, windows_for
from .hygiene_rules import Rhythm, occurrences, starter_plan
from .tables import equipment, hygiene_task, hygiene_task_done

HISTORY_DAYS = 21


def _open(day: date) -> bool:
    return bool(windows_for(DEFAULT_WEEKLY_HOURS, day))


def seed_hygiene(
    conn: Connection, *, practice_id: int, user_id: int, user_name: str, specialty: str, arabic: bool, now: datetime,
    rng: random.Random,
) -> None:
    today = now.astimezone(TUNIS).date()
    plan = starter_plan(specialty)
    keys = {
        e.key: conn.execute(
            insert(equipment).values(practice_id=practice_id, name=e.name_ar if arabic else e.name_fr, kind=e.kind,
                                     serial_number=f"SN-{rng.randint(10000, 99999)}", created_at=now)
            .returning(equipment.c.id)
        ).scalar_one()
        for e in plan.equipment
    }
    overdue = next((t for t in plan.tasks if t.frequency == "yearly"), None) or next(
        (t for t in plan.tasks if t.frequency == "monthly"), None)
    proofs = []
    for n, t in enumerate(plan.tasks):
        if t is overdue:
            starts_on = today - timedelta(days=3)
        elif t.frequency == "yearly":
            starts_on = today + timedelta(days=30)
        elif t.frequency == "monthly":
            starts_on = today - timedelta(days=14)
        else:
            starts_on = today - timedelta(days=HISTORY_DAYS)
        task_id = conn.execute(
            insert(hygiene_task).values(
                practice_id=practice_id, title=t.title_ar if arabic else t.title_fr,
                equipment_id=keys.get(t.equipment) if t.equipment else None, frequency=t.frequency, weekday=t.weekday,
                interval_days=t.interval_days, starts_on=starts_on,
                instructions=t.instructions_ar if arabic else t.instructions_fr, created_at=now - timedelta(days=HISTORY_DAYS),
            ).returning(hygiene_task.c.id)
        ).scalar_one()
        if t is overdue:
            continue
        rhythm = Rhythm(t.frequency, starts_on=starts_on, weekday=t.weekday, interval_days=t.interval_days)
        past = occurrences(rhythm, starts_on, today, _open)
        open_days = [d for d in past if d < today and t.frequency == "daily"]
        forgotten = open_days[-2] if n == 0 and len(open_days) >= 2 else None
        tested = [d for d in past if d < today and t.frequency == "weekly" and t.equipment == "autoclave"]
        for day in past:
            if day == forgotten:
                continue
            if day == today:
                if n % 2 == 1 or now < at_tunis(today, time(8, 30)):
                    continue
                done_at = min(now, at_tunis(today, time(8, 0)) + timedelta(minutes=rng.randint(0, 25)))
            else:
                done_at = at_tunis(day, time(8, 0)) + timedelta(minutes=rng.randint(0, 40))
            failed = bool(tested) and day == tested[0]
            proofs.append({
                "practice_id": practice_id, "task_id": task_id, "due_on": day, "done_by": user_id,
                "done_by_name": user_name, "done_at": done_at, "result": "not_ok" if failed else "ok",
                "note": ("Indicateur non viré – cycle relancé, 2e test conforme" if not arabic
                         else "المؤشر لم يتغيّر – أُعيدت الدورة، الاختبار الثاني مطابق") if failed else "",
            })
    if proofs:
        conn.execute(insert(hygiene_task_done), proofs)
