"""``/api/hygiene`` – sterilisation cycles, their packs and the traceability of the packs (spec stock-hygiène 3, 5.3,
8). Codes, dates and states: :mod:`daftar.label_rules`; the label settings (formats, shelf lives): :mod:`daftar.labels`.

Roles (section 3): every staff role records cycles, prints their labels and notes which pack was opened for which
patient; the owner corrects or deletes a cycle (with a reason, in the change log) and searches the traceability
("who got pack X?", "which packs did patient Y get?").

- ``GET /cycles/setup`` → ``{autoclaves:[{id, name, labelCode, nextNumber, lastRunAt}], programs, contents}``: the
  active autoclaves with the next cycle number, the practice's last programs and pack contents first, then the
  usual ones of the specialty (in the user's language).
- ``POST /cycles {equipmentId, number?, runAt?, program, result: ok|not_ok, packs:[{content, packaging, quantity}],
  packCount?, note?}`` → 201 Cycle. The autoclave gets its label code (``A1`` …) at its first cycle; the number is
  the next one unless given (409 ``cycle_number_taken``). "Conforme": one pack per unit of ``quantity`` (at most 99,
  422 ``too_many_packs``), each with its code and "à utiliser avant" (sterilised day + shelf life of its packaging).
  "Non conforme": no pack and no label (422 ``cycle_not_ok`` with packs) – only ``packCount``, the load to sterilise
  again. 422 ``not_an_autoclave`` / ``equipment_inactive`` / ``invalid_equipment`` / ``run_in_future`` /
  ``run_too_old`` (more than a year back).
- ``GET /cycles?from=&to=&equipmentId=`` (at most 366 days, default the last 30) → ``{from, to, cycles}``, newest
  first; ``GET /cycles/{id}``. Each pack carries its state (usable, expired, used, not_sterile) and its use.
- ``PATCH /cycles/{id} {result?, program?, note?, reason}`` (owner): logged old → new. A cycle found "non conforme"
  afterwards (biological indicator) recalls its packs: they are refused from then on, the traceability names the
  patients who already got one.
- ``DELETE /cycles/{id} {reason}`` (owner): only while none of its packs was used (409 ``cycle_in_use``); logged.
- ``GET /packs?q=&limit=`` → the packs the desk may mean: nothing typed – the usable packs, newest first; a code or a
  part of it (``A1-0412-07``, ``412-7``, ``0412``) – those packs; other text – contents. Usable ones first.
- ``POST /pack-uses {code, appointmentId?, patientId?}`` → 201 Use: the pack was opened for this patient (and
  appointment). Refused with a clear text: 422 ``pack_unknown``, ``pack_expired`` (+ ``expiresOn``),
  ``pack_not_sterile`` (cycle non conforme); 409 ``pack_used`` (+ ``patientName``, ``usedAt``). Never required: the
  appointment goes on without it.
- ``GET /pack-uses?appointmentId=`` (staff) or ``?patientId=`` (owner) → ``[Use]``, newest first.
- ``DELETE /pack-uses/{id} {reason?}``: its author within 15 minutes (a wrong code), the owner always with a reason;
  logged.
- ``GET /trace?code=`` (owner) → ``{pack, use}`` · ``GET /trace?patientId=`` → ``{patient:{id, name}, uses}``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Query, Response
from pydantic import Field, StrictInt, model_validator
from sqlalchemy import Connection, delete, exists, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import audit
from .clock import TUNIS, today_tunis
from .db import constraint_name
from .deps import Conn, Ctx, OwnerUser, OwnerWriter, Principal, StaffUser, StaffWriter
from .label_rules import (
    DEFAULT_PROGRAMS,
    MAX_PACKS,
    Packaging,
    PackState,
    initials,
    label_settings,
    next_label_code,
    pack_code,
    pack_contents,
    pack_query,
    pack_state,
    sterile_until,
)
from .problems import ApiError, conflict, forbidden, not_found, unprocessable
from .schemas import ApiModel, InstantIn, TunisDateTime
from .tables import (
    appointment,
    equipment,
    patient,
    practice,
    sterile_pack,
    sterile_pack_use,
    sterilization_cycle,
)

router = APIRouter(prefix="/api/hygiene", tags=["sterilization"])

UNDO_WINDOW = timedelta(minutes=15)
MAX_DAYS = 366
#: First key of ``pg_advisory_xact_lock(key, practice_id)``: autoclave codes and cycle numbers, one after the other.
CYCLE_LOCK = 0x57E21
Result = Literal["ok", "not_ok"]
Content = Annotated[str, Field(min_length=1, max_length=60)]
Program = Annotated[str, Field(max_length=60)]
Note = Annotated[str, Field(max_length=500)]
Reason = Annotated[str, Field(max_length=300)]
RequiredReason = Annotated[str, Field(min_length=1, max_length=300)]
CycleNumber = Annotated[StrictInt, Field(ge=1, le=999_999)]
STATE_ORDER = {"usable": 0, "expired": 1, "used": 2, "not_sterile": 3}


# --- models -------------------------------------------------------------------------------------------------------


class CycleRef(ApiModel):
    id: int
    label_code: str
    number: int
    equipment_name: str
    run_at: TunisDateTime
    result: Result


class UseOut(ApiModel):
    id: int
    pack_id: int
    code: str
    content: str
    packaging: Packaging
    expires_on: date
    cycle: CycleRef
    patient_id: int
    patient_name: str
    appointment_id: int | None
    used_at: TunisDateTime
    used_by: str
    undoable: bool


class PackUse(ApiModel):
    id: int
    patient_id: int
    patient_name: str
    appointment_id: int | None
    used_at: TunisDateTime
    used_by: str


class PackOut(ApiModel):
    id: int
    seq: int
    code: str
    content: str
    packaging: Packaging
    expires_on: date
    state: PackState
    use: PackUse | None


class PackFound(PackOut):
    cycle_id: int
    label_code: str
    number: int
    equipment_name: str
    run_at: TunisDateTime


class CycleOut(ApiModel):
    id: int
    equipment_id: int
    equipment_name: str
    label_code: str
    number: int
    run_at: TunisDateTime
    program: str
    result: Result
    pack_count: int
    note: str
    performed_by: str
    initials: str
    created_at: TunisDateTime
    packs: list[PackOut]


class CycleList(ApiModel):
    from_: date = Field(alias="from")
    to: date
    cycles: list[CycleOut]


class AutoclaveOut(ApiModel):
    id: int
    name: str
    label_code: str | None
    next_number: int
    last_run_at: TunisDateTime | None


class CycleSetup(ApiModel):
    autoclaves: list[AutoclaveOut]
    programs: list[str]
    contents: list[str]


class PackLineIn(ApiModel):
    content: Content
    packaging: Packaging = "sachet"
    quantity: Annotated[StrictInt, Field(ge=1, le=MAX_PACKS)]


class CycleIn(ApiModel):
    equipment_id: int
    number: CycleNumber | None = None
    run_at: InstantIn | None = None
    program: Program = ""
    result: Result
    packs: Annotated[list[PackLineIn], Field(max_length=20)] = []
    pack_count: Annotated[StrictInt, Field(ge=0, le=MAX_PACKS)] | None = None
    note: Note = ""


class CycleCorrection(ApiModel):
    result: Result | None = None
    program: Program | None = None
    note: Note | None = None
    reason: RequiredReason


class ReasonIn(ApiModel):
    reason: RequiredReason


class UseIn(ApiModel):
    code: Annotated[str, Field(min_length=1, max_length=40)]
    appointment_id: int | None = None
    patient_id: int | None = None

    @model_validator(mode="after")
    def _for_whom(self) -> UseIn:
        if self.appointment_id is None and self.patient_id is None:
            raise ValueError("validation: Indiquez le rendez-vous ou le patient.")
        return self


class UndoIn(ApiModel):
    reason: Reason = ""


class TracePatient(ApiModel):
    id: int
    name: str


class PackTrace(ApiModel):
    pack: PackFound
    use: UseOut | None


class PatientTrace(ApiModel):
    patient: TracePatient
    uses: list[UseOut]


# --- reading ------------------------------------------------------------------------------------------------------


def _name(first: str, last: str) -> str:
    return f"{first} {last}".strip()


def _pack_rows(conn: Connection, practice_id: int, *conditions: Any, limit: int | None = None) -> list[Any]:
    """Packs with their cycle, autoclave and use (patient name) – every reading of packs goes through here."""
    query = (
        select(
            sterile_pack, sterilization_cycle.c.number, sterilization_cycle.c.run_at, sterilization_cycle.c.result,
            equipment.c.name.label("equipment_name"), equipment.c.label_code,
            sterile_pack_use.c.id.label("use_id"), sterile_pack_use.c.patient_id, sterile_pack_use.c.appointment_id,
            sterile_pack_use.c.used_at, sterile_pack_use.c.used_by.label("used_by_id"), sterile_pack_use.c.used_by_name,
            patient.c.first_name, patient.c.last_name,
        )
        .select_from(
            sterile_pack.join(sterilization_cycle, sterilization_cycle.c.id == sterile_pack.c.cycle_id)
            .join(equipment, equipment.c.id == sterilization_cycle.c.equipment_id)
            .outerjoin(sterile_pack_use, sterile_pack_use.c.pack_id == sterile_pack.c.id)
            .outerjoin(patient, patient.c.id == sterile_pack_use.c.patient_id)
        )
        .where(sterile_pack.c.practice_id == practice_id, *conditions)
        .order_by(sterilization_cycle.c.run_at.desc(), sterilization_cycle.c.id.desc(), sterile_pack.c.seq)
    )
    if limit is not None:
        query = query.limit(limit)
    return list(conn.execute(query).all())


def _state(row: Any, today: date) -> PackState:
    return pack_state(result=row.result, used=row.use_id is not None, expires_on=row.expires_on, today=today)


def _pack_use(row: Any) -> PackUse | None:
    if row.use_id is None:
        return None
    return PackUse(id=row.use_id, patient_id=row.patient_id, patient_name=_name(row.first_name, row.last_name),
                   appointment_id=row.appointment_id, used_at=row.used_at, used_by=row.used_by_name)


def _pack(row: Any, today: date) -> PackOut:
    return PackOut(id=row.id, seq=row.seq, code=row.code, content=row.content, packaging=row.packaging,
                   expires_on=row.expires_on, state=_state(row, today), use=_pack_use(row))


def _found(row: Any, today: date) -> PackFound:
    return PackFound(**_pack(row, today).model_dump(), cycle_id=row.cycle_id, label_code=row.label_code,
                     number=row.number, equipment_name=row.equipment_name, run_at=row.run_at)


def load_cycles(conn: Connection, practice_id: int, today: date, *conditions: Any) -> list[CycleOut]:
    rows = conn.execute(
        select(sterilization_cycle, equipment.c.name.label("equipment_name"), equipment.c.label_code)
        .select_from(sterilization_cycle.join(equipment, equipment.c.id == sterilization_cycle.c.equipment_id))
        .where(sterilization_cycle.c.practice_id == practice_id, *conditions)
        .order_by(sterilization_cycle.c.run_at.desc(), sterilization_cycle.c.id.desc())
    ).all()
    if not rows:
        return []
    packs: dict[int, list[PackOut]] = {r.id: [] for r in rows}
    for p in _pack_rows(conn, practice_id, sterile_pack.c.cycle_id.in_(list(packs))):
        packs[p.cycle_id].append(_pack(p, today))
    return [
        CycleOut(id=r.id, equipment_id=r.equipment_id, equipment_name=r.equipment_name, label_code=r.label_code,
                 number=r.number, run_at=r.run_at, program=r.program, result=r.result, pack_count=r.pack_count,
                 note=r.note, performed_by=r.performed_by_name, initials=r.initials, created_at=r.created_at,
                 packs=packs[r.id])
        for r in rows
    ]


def _cycle(conn: Connection, practice_id: int, cycle_id: int, today: date) -> CycleOut:
    found = load_cycles(conn, practice_id, today, sterilization_cycle.c.id == cycle_id)
    if not found:
        raise not_found()
    return found[0]


def _use_rows(conn: Connection, practice_id: int, *conditions: Any) -> list[Any]:
    return _pack_rows(conn, practice_id, sterile_pack_use.c.id.is_not(None), *conditions)


def _undoable(user: Principal, row: Any, now: datetime) -> bool:
    return user.is_owner or (row.used_by_id == user.user_id and now - row.used_at <= UNDO_WINDOW)


def _use(user: Principal, row: Any, now: datetime) -> UseOut:
    return UseOut(
        id=row.use_id, pack_id=row.id, code=row.code, content=row.content, packaging=row.packaging,
        expires_on=row.expires_on,
        cycle=CycleRef(id=row.cycle_id, label_code=row.label_code, number=row.number, equipment_name=row.equipment_name,
                       run_at=row.run_at, result=row.result),
        patient_id=row.patient_id, patient_name=_name(row.first_name, row.last_name), appointment_id=row.appointment_id,
        used_at=row.used_at, used_by=row.used_by_name, undoable=_undoable(user, row, now),
    )


def _sorted_uses(user: Principal, rows: list[Any], now: datetime) -> list[UseOut]:
    return [_use(user, r, now) for r in sorted(rows, key=lambda r: (r.used_at, r.use_id), reverse=True)]


# --- cycles -------------------------------------------------------------------------------------------------------


def _recent_programs(conn: Connection, practice_id: int) -> list[str]:
    """The practice's last programs, newest first."""
    return list(conn.execute(
        select(sterilization_cycle.c.program)
        .where(sterilization_cycle.c.practice_id == practice_id, sterilization_cycle.c.program != "")
        .group_by(sterilization_cycle.c.program).order_by(func.max(sterilization_cycle.c.run_at).desc()).limit(5)
    ).scalars())


def _recent_contents(conn: Connection, practice_id: int) -> list[str]:
    """The practice's last pack contents, newest first."""
    return list(conn.execute(
        select(sterile_pack.c.content)
        .select_from(sterile_pack.join(sterilization_cycle, sterilization_cycle.c.id == sterile_pack.c.cycle_id))
        .where(sterile_pack.c.practice_id == practice_id)
        .group_by(sterile_pack.c.content).order_by(func.max(sterilization_cycle.c.run_at).desc()).limit(8)
    ).scalars())


def _unique(*groups: list[str] | tuple[str, ...], limit: int) -> list[str]:
    seen: dict[str, str] = {}
    for group in groups:
        for value in group:
            seen.setdefault(value.lower(), value)
    return list(seen.values())[:limit]


@router.get("/cycles/setup")
def cycle_setup(user: StaffUser, conn: Conn) -> CycleSetup:
    numbers = (
        select(sterilization_cycle.c.equipment_id, func.max(sterilization_cycle.c.number).label("last"),
               func.max(sterilization_cycle.c.run_at).label("last_run_at"))
        .where(sterilization_cycle.c.practice_id == user.pid).group_by(sterilization_cycle.c.equipment_id).subquery()
    )
    rows = conn.execute(
        select(equipment.c.id, equipment.c.name, equipment.c.label_code, numbers.c.last, numbers.c.last_run_at)
        .select_from(equipment.outerjoin(numbers, numbers.c.equipment_id == equipment.c.id))
        .where(equipment.c.practice_id == user.pid, equipment.c.kind == "autoclave", equipment.c.active.is_(True))
        .order_by(func.lower(equipment.c.name), equipment.c.id)
    ).all()
    specialty = conn.execute(select(practice.c.specialty).where(practice.c.id == user.pid)).scalar_one()
    return CycleSetup(
        autoclaves=[AutoclaveOut(id=r.id, name=r.name, label_code=r.label_code, next_number=(r.last or 0) + 1,
                                 last_run_at=r.last_run_at) for r in rows],
        programs=_unique(_recent_programs(conn, user.pid), DEFAULT_PROGRAMS, limit=8),
        contents=_unique(_recent_contents(conn, user.pid), pack_contents(specialty, user.lang), limit=14),
    )


def _autoclave(conn: Connection, practice_id: int, equipment_id: int) -> Any:
    row = conn.execute(
        select(equipment).where(equipment.c.id == equipment_id, equipment.c.practice_id == practice_id).with_for_update()
    ).first()
    if row is None:
        raise unprocessable("Cet équipement n'existe pas dans le cabinet.", code="invalid_equipment")
    if row.kind != "autoclave":
        raise unprocessable("Choisissez un autoclave.", code="not_an_autoclave")
    if not row.active:
        raise unprocessable("Cet autoclave est désactivé.", code="equipment_inactive")
    return row


@router.post("/cycles", status_code=201)
def create_cycle(body: CycleIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> CycleOut:
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    run_at = body.run_at or now
    if run_at > now + timedelta(minutes=5):
        raise unprocessable("Ce cycle est dans le futur.", code="run_in_future")
    if run_at < now - timedelta(days=MAX_DAYS):
        raise unprocessable("Ce cycle a plus d'un an.", code="run_too_old")
    if body.result == "not_ok" and body.packs:
        raise unprocessable("Cycle non conforme : pas d'étiquettes, recommencez le cycle.", code="cycle_not_ok")
    total = sum(line.quantity for line in body.packs)
    if total > MAX_PACKS:
        raise unprocessable(f"{MAX_PACKS} paquets au plus par cycle.", code="too_many_packs")
    conn.execute(select(func.pg_advisory_xact_lock(CYCLE_LOCK, user.pid)))
    gear = _autoclave(conn, user.pid, body.equipment_id)
    code = gear.label_code
    if code is None:
        taken = conn.execute(select(equipment.c.label_code).where(equipment.c.practice_id == user.pid,
                                                                  equipment.c.label_code.is_not(None))).scalars()
        code = next_label_code(list(taken))
        conn.execute(update(equipment).where(equipment.c.id == gear.id).values(label_code=code))
    number = body.number
    if number is None:
        last = conn.execute(select(func.max(sterilization_cycle.c.number))
                            .where(sterilization_cycle.c.equipment_id == gear.id)).scalar_one()
        number = (last or 0) + 1
    settings = label_settings(conn.execute(select(practice.c.label_settings).where(practice.c.id == user.pid)).scalar_one())
    try:
        with conn.begin_nested():
            cycle_id = conn.execute(
                insert(sterilization_cycle).values(
                    practice_id=user.pid, equipment_id=gear.id, number=number, run_at=run_at, program=body.program,
                    result=body.result, pack_count=total if body.result == "ok" else (body.pack_count or 0),
                    note=body.note, performed_by=user.user_id, performed_by_name=user.name[:120],
                    initials=initials(user.name), created_at=now,
                ).returning(sterilization_cycle.c.id)
            ).scalar_one()
    except IntegrityError as exc:
        if constraint_name(exc) == "sterilization_cycle_number_key":
            raise conflict(f"Le cycle n° {number} de cet autoclave existe déjà.", code="cycle_number_taken") from exc
        raise
    sterilised_on = run_at.astimezone(TUNIS).date()
    packs, seq = [], 0
    for line in body.packs:
        for _ in range(line.quantity):
            seq += 1
            packs.append({
                "practice_id": user.pid, "cycle_id": cycle_id, "seq": seq, "code": pack_code(code, number, seq),
                "content": line.content, "packaging": line.packaging,
                "expires_on": sterile_until(sterilised_on, settings["shelf_life_days"][line.packaging]),
            })
    if packs:
        conn.execute(insert(sterile_pack), packs)
    return _cycle(conn, user.pid, cycle_id, today)


@router.get("/cycles")
def list_cycles(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    first: Annotated[date | None, Query(alias="from")] = None,
    last: Annotated[date | None, Query(alias="to")] = None,
    equipment_id: Annotated[int | None, Query(alias="equipmentId")] = None,
) -> CycleList:
    today = today_tunis(ctx.clock)
    last = last or today
    first = first or last - timedelta(days=29)
    if last < first or (last - first).days >= MAX_DAYS:
        raise unprocessable("Choisissez une période d'un an au plus.", code="invalid_range")
    start = datetime.combine(first, datetime.min.time(), tzinfo=TUNIS)
    end = datetime.combine(last + timedelta(days=1), datetime.min.time(), tzinfo=TUNIS)
    conditions = [sterilization_cycle.c.run_at >= start, sterilization_cycle.c.run_at < end]
    if equipment_id is not None:
        conditions.append(sterilization_cycle.c.equipment_id == equipment_id)
    return CycleList(from_=first, to=last, cycles=load_cycles(conn, user.pid, today, *conditions))


@router.get("/cycles/{cycle_id}")
def get_cycle(cycle_id: int, user: StaffUser, ctx: Ctx, conn: Conn) -> CycleOut:
    return _cycle(conn, user.pid, cycle_id, today_tunis(ctx.clock))


def _cycle_name(c: CycleOut) -> str:
    return f"{c.label_code} n° {c.number}"


@router.patch("/cycles/{cycle_id}")
def correct_cycle(cycle_id: int, body: CycleCorrection, user: OwnerWriter, ctx: Ctx, conn: Conn) -> CycleOut:
    today = today_tunis(ctx.clock)
    current = _cycle(conn, user.pid, cycle_id, today)
    values = {k: v for k, v in body.model_dump(exclude_unset=True, by_alias=False).items()
              if k in ("result", "program", "note") and v is not None}
    before, after = audit.diff(current.model_dump(by_alias=False), values,
                               {"result": "result", "program": "program", "note": "note"})
    if after:
        conn.execute(update(sterilization_cycle).where(sterilization_cycle.c.id == cycle_id).values(**values))
        audit.record(conn, user, entity="sterilization_cycle", entity_id=cycle_id, action="update", now=ctx.clock.now(),
                     before={"cycle": _cycle_name(current), **before}, after=after, reason=body.reason.strip())
    return _cycle(conn, user.pid, cycle_id, today)


@router.delete("/cycles/{cycle_id}", status_code=204)
def delete_cycle(cycle_id: int, body: ReasonIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> Response:
    current = _cycle(conn, user.pid, cycle_id, today_tunis(ctx.clock))
    if any(p.use is not None for p in current.packs):
        raise conflict("Un paquet de ce cycle a déjà été utilisé : corrigez le cycle plutôt.", code="cycle_in_use")
    audit.record(conn, user, entity="sterilization_cycle", entity_id=cycle_id, action="delete", now=ctx.clock.now(),
                 before={"cycle": _cycle_name(current), "equipment": current.equipment_name, "runAt": current.run_at,
                         "program": current.program, "result": current.result, "packCount": current.pack_count,
                         "performedBy": current.performed_by},
                 reason=body.reason.strip())
    conn.execute(delete(sterilization_cycle).where(sterilization_cycle.c.id == cycle_id,
                                                   sterilization_cycle.c.practice_id == user.pid))
    return Response(status_code=204)


# --- packs and their use ------------------------------------------------------------------------------------------


def _query_conditions(q: str) -> list[Any]:
    parsed = pack_query(q)
    if parsed is None:
        words = q.strip()
        return [or_(sterile_pack.c.content.icontains(words, autoescape=True),
                    sterile_pack.c.code.icontains(words.upper(), autoescape=True))]
    if parsed.code is not None:
        return [sterile_pack.c.code == parsed.code]
    conditions = [sterilization_cycle.c.number == parsed.number]
    if parsed.seq is not None:
        conditions.append(sterile_pack.c.seq == parsed.seq)
    if parsed.device is not None:
        conditions.append(equipment.c.label_code == parsed.device)
    return conditions


@router.get("/packs")
def find_packs(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    q: Annotated[str, Query(max_length=40)] = "",
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[PackFound]:
    today = today_tunis(ctx.clock)
    if q.strip():
        rows = _pack_rows(conn, user.pid, *_query_conditions(q), limit=60)
    else:
        rows = _pack_rows(conn, user.pid, sterilization_cycle.c.result == "ok", sterile_pack_use.c.id.is_(None),
                          sterile_pack.c.expires_on > today, limit=limit)
    found = [_found(r, today) for r in rows]
    found.sort(key=lambda p: STATE_ORDER[p.state])  # stable: newest cycle first within a state
    return found[:limit]


def _whom(conn: Connection, practice_id: int, body: UseIn) -> tuple[int, int | None]:
    """The patient (and appointment) a pack is used for – 422 ``invalid_appointment`` / ``invalid_patient``."""
    if body.appointment_id is not None:
        found = conn.execute(select(appointment.c.patient_id).where(appointment.c.id == body.appointment_id,
                                                                    appointment.c.practice_id == practice_id)).first()
        if found is None:
            raise unprocessable("Rendez-vous introuvable dans le cabinet.", code="invalid_appointment")
        if body.patient_id is not None and body.patient_id != found.patient_id:
            raise unprocessable("Ce patient n'est pas celui du rendez-vous.", code="invalid_patient")
        return found.patient_id, body.appointment_id
    known = conn.execute(select(exists().where(patient.c.id == body.patient_id,
                                               patient.c.practice_id == practice_id))).scalar_one()
    if not known:
        raise unprocessable("Patient introuvable dans le cabinet.", code="invalid_patient")
    return int(body.patient_id or 0), None


def _fr_day(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _refuse(row: Any, today: date) -> None:
    state = _state(row, today)
    if state == "not_sterile":
        raise ApiError(422, f"Cycle non conforme ({row.label_code} n° {row.number}) : ce paquet n'est pas stérile. "
                            "Ne l'utilisez pas, restérilisez-le.", code="pack_not_sterile",
                       extra={"cycleNumber": row.number})
    if state == "used":
        raise ApiError(409, f"Ce paquet est déjà utilisé (le {_fr_day(row.used_at.astimezone(TUNIS).date())}).",
                       code="pack_used",
                       extra={"patientName": _name(row.first_name, row.last_name),
                              "usedAt": audit.jsonable(row.used_at)})
    if state == "expired":
        raise ApiError(422, f"Paquet périmé (à utiliser avant le {_fr_day(row.expires_on)}) : ne l'utilisez pas, "
                            "restérilisez-le.", code="pack_expired", extra={"expiresOn": row.expires_on.isoformat()})


def _unknown() -> ApiError:
    return unprocessable("Code inconnu : vérifiez l'étiquette du paquet.", code="pack_unknown")


@router.post("/pack-uses", status_code=201)
def use_pack(body: UseIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> UseOut:
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    patient_id, appointment_id = _whom(conn, user.pid, body)
    parsed = pack_query(body.code)
    if parsed is None or parsed.code is None:
        raise _unknown()
    pack_id = conn.execute(
        select(sterile_pack.c.id).where(sterile_pack.c.practice_id == user.pid, sterile_pack.c.code == parsed.code)
        .with_for_update()
    ).scalar_one_or_none()
    if pack_id is None:
        raise _unknown()
    (row,) = _pack_rows(conn, user.pid, sterile_pack.c.id == pack_id)
    _refuse(row, today)
    try:
        with conn.begin_nested():
            conn.execute(insert(sterile_pack_use).values(
                practice_id=user.pid, pack_id=pack_id, patient_id=patient_id, appointment_id=appointment_id, used_at=now,
                used_by=user.user_id, used_by_name=user.name[:120]))
    except IntegrityError as exc:
        if constraint_name(exc) == "sterile_pack_use_once":
            raise conflict("Ce paquet est déjà utilisé.", code="pack_used") from exc
        raise
    (used,) = _use_rows(conn, user.pid, sterile_pack.c.id == pack_id)
    return _use(user, used, now)


@router.get("/pack-uses")
def list_uses(
    user: StaffUser,
    ctx: Ctx,
    conn: Conn,
    appointment_id: Annotated[int | None, Query(alias="appointmentId")] = None,
    patient_id: Annotated[int | None, Query(alias="patientId")] = None,
) -> list[UseOut]:
    if appointment_id is not None:
        rows = _use_rows(conn, user.pid, sterile_pack_use.c.appointment_id == appointment_id)
    elif patient_id is not None:
        if not user.is_owner:
            raise forbidden()
        rows = _use_rows(conn, user.pid, sterile_pack_use.c.patient_id == patient_id)
    else:
        raise unprocessable("Indiquez le rendez-vous ou le patient.")
    return _sorted_uses(user, rows, ctx.clock.now())



@router.delete("/pack-uses/{use_id}", status_code=204)
def undo_use(use_id: int, user: StaffWriter, ctx: Ctx, conn: Conn,
             body: Annotated[UndoIn | None, Body()] = None) -> Response:
    rows = _use_rows(conn, user.pid, sterile_pack_use.c.id == use_id)
    if not rows:
        raise not_found()
    row, now = rows[0], ctx.clock.now()
    quick = row.used_by_id == user.user_id and now - row.used_at <= UNDO_WINDOW
    if not (quick or user.is_owner):
        if row.used_by_id == user.user_id:
            raise forbidden("Seule la personne titulaire peut annuler après 15 minutes.", code="undo_too_late")
        raise forbidden()
    reason = body.reason.strip() if body else ""
    if not quick and not reason:
        raise unprocessable("Indiquez le motif de l'annulation.", code="reason_required")
    audit.record(conn, user, entity="sterile_pack_use", entity_id=use_id, action="delete", now=now,
                 before={"code": row.code, "content": row.content, "patient": _name(row.first_name, row.last_name),
                         "usedAt": row.used_at, "usedBy": row.used_by_name},
                 reason=reason)
    conn.execute(delete(sterile_pack_use).where(sterile_pack_use.c.id == use_id))
    return Response(status_code=204)


# --- traceability (owner) -----------------------------------------------------------------------------------------


@router.get("/trace")
def trace(
    user: OwnerUser,
    ctx: Ctx,
    conn: Conn,
    code: Annotated[str | None, Query(max_length=40)] = None,
    patient_id: Annotated[int | None, Query(alias="patientId")] = None,
) -> PackTrace | PatientTrace:
    now, today = ctx.clock.now(), today_tunis(ctx.clock)
    if code is not None:
        parsed = pack_query(code)
        if parsed is None or parsed.code is None:
            raise not_found()
        rows = _pack_rows(conn, user.pid, sterile_pack.c.code == parsed.code)
        if not rows:
            raise not_found()
        row = rows[0]
        return PackTrace(pack=_found(row, today), use=_use(user, row, now) if row.use_id is not None else None)
    if patient_id is not None:
        person = conn.execute(select(patient.c.first_name, patient.c.last_name)
                              .where(patient.c.id == patient_id, patient.c.practice_id == user.pid)).first()
        if person is None:
            raise not_found()
        rows = _use_rows(conn, user.pid, sterile_pack_use.c.patient_id == patient_id)
        return PatientTrace(patient=TracePatient(id=patient_id, name=_name(person.first_name, person.last_name)),
                            uses=_sorted_uses(user, rows, now))
    raise unprocessable("Indiquez un code de paquet ou un patient.")


def cycles_of(conn: Connection, equipment_id: int) -> int:
    """How many cycles an autoclave has (it then stays in the register)."""
    return int(conn.execute(select(func.count()).where(sterilization_cycle.c.equipment_id == equipment_id)).scalar_one())

