"""Demo practices (sections 5, 12, 15): ``POST /api/demo {lang?, specialty?}`` → 201 ``{token, user}``.

Every visitor gets an own practice (``is_demo``, slug ``demo-<8>``, expires after 24 h) owned by
``demo-<random>@demo.daftar.invalid`` and filled with invented data relative to today: 25 patients with Tunisian
names (Arabic script in an Arabic demo) and phone numbers ``+21600000001…`` (the prefix 00 does not exist),
a family sharing one number, medical alerts, appointments from −14 to +7 days (done, no-show, cancelled, confirmed,
online requests), today's waiting room (3 waiting, 1 in treatment), acts, instalments and a deposit, tomorrow's
reminders, and recurring sessions for physiotherapists and psychologists. Appointments are written directly
into the tables and never overlap (the database's EXCLUDE constraints would refuse them).

Limits: 5 demos per IP and hour, 300 per day in total → 429. The job ``demo-cleanup`` (every 30 min) deletes expired
demo practices with everything in them (ON DELETE CASCADE).
"""

from __future__ import annotations

import random
import secrets
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body
from sqlalchemy import Connection, delete, insert, select

from .auth import Session, session_for
from .catalog import Specialty, insert_default_services
from .clock import TUNIS, at_tunis
from .context import AppContext
from .deps import ClientIp, Conn, Ctx
from .hours import DEFAULT_WEEKLY_HOURS, windows_for
from .passwords import hash_password
from .problems import too_many_requests
from .schemas import ApiModel, Lang
from .slugs import demo_slug
from .tables import app_user, appointment, patient, payment, practice, practitioner, queue_entry, service, treatment

router = APIRouter(prefix="/api/demo", tags=["demo"])

PER_IP = 5
GLOBAL_PER_DAY = 300
DEMO_TTL = timedelta(hours=24)
PATIENTS = 25
TOO_MANY = "Trop de démos lancées. Veuillez réessayer plus tard."


class DemoIn(ApiModel):
    lang: Lang = "fr"
    specialty: Specialty = "generaliste"


# --- invented reference data -----------------------------------------------------------------------------------

PRACTICE_NAMES: dict[str, tuple[str, str]] = {
    "generaliste": ("Cabinet Médical Démo", "عيادة طبية تجريبية"),
    "dentiste": ("Cabinet Dentaire Démo", "عيادة أسنان تجريبية"),
    "pediatre": ("Cabinet de Pédiatrie Démo", "عيادة أطفال تجريبية"),
    "gynecologue": ("Cabinet de Gynécologie Démo", "عيادة نساء وتوليد تجريبية"),
    "dermatologue": ("Cabinet de Dermatologie Démo", "عيادة جلدية تجريبية"),
    "ophtalmologue": ("Cabinet d'Ophtalmologie Démo", "عيادة عيون تجريبية"),
    "cardiologue": ("Cabinet de Cardiologie Démo", "عيادة قلب تجريبية"),
    "orl": ("Cabinet ORL Démo", "عيادة أنف وأذن وحنجرة تجريبية"),
    "kinesitherapeute": ("Cabinet de Kinésithérapie Démo", "مركز علاج طبيعي تجريبي"),
    "psychologue": ("Cabinet de Psychologie Démo", "عيادة نفسية تجريبية"),
    "autre": ("Cabinet Démo", "عيادة تجريبية"),
}
#: (title, name) of the practitioners per specialty; others get one doctor.
PRACTITIONERS: dict[str, list[tuple[str, str]]] = {
    "generaliste": [("Dr.", "Salah Ben Amor"), ("Dr.", "Ines Chaabane")],
    "dentiste": [("Dr.", "Karim Mansouri"), ("Dr.", "Rim Belhadj")],
    "kinesitherapeute": [("", "Mehdi Gharbi"), ("", "Salma Riahi")],
    "psychologue": [("", "Asma Zouari")],
    "pediatre": [("Dr.", "Leila Hammami")],
}
DEFAULT_PRACTITIONERS = [("Dr.", "Sami Khelifi")]
FEMALE = [("Amira", "أميرة"), ("Ines", "إيناس"), ("Salma", "سلمى"), ("Mariem", "مريم"), ("Rim", "ريم"),
          ("Nour", "نور"), ("Yasmine", "ياسمين"), ("Leila", "ليلى"), ("Sonia", "سنية"), ("Hela", "هالة"),
          ("Fatma", "فاطمة"), ("Asma", "أسماء"), ("Olfa", "ألفة")]
MALE = [("Mohamed", "محمد"), ("Ahmed", "أحمد"), ("Sami", "سامي"), ("Karim", "كريم"), ("Youssef", "يوسف"),
        ("Mehdi", "مهدي"), ("Anis", "أنيس"), ("Hamza", "حمزة"), ("Walid", "وليد"), ("Skander", "سكندر"),
        ("Bilel", "بلال"), ("Nizar", "نزار")]
LAST = [("Trabelsi", "الطرابلسي"), ("Ben Ali", "بن علي"), ("Gharbi", "الغربي"), ("Jlassi", "الجلاصي"),
        ("Hammami", "الحمامي"), ("Bouazizi", "البوعزيزي"), ("Mejri", "الماجري"), ("Ayari", "العياري"),
        ("Chaabane", "شعبان"), ("Ben Amor", "بن عمر"), ("Dridi", "الدريدي"), ("Sassi", "الساسي"),
        ("Khelifi", "الخليفي"), ("Riahi", "الرياحي"), ("Ferchichi", "الفرشيشي"), ("Mansouri", "المنصوري"),
        ("Zouari", "الزواري"), ("Baccouche", "بكوش"), ("Belhadj", "بالحاج"), ("Karoui", "القروي"),
        ("Mzali", "مزالي"), ("Saidi", "السعيدي"), ("Hamdi", "حمدي"), ("Ouni", "العوني"), ("Tlili", "التليلي")]
ALERTS = {
    3: ("Allergie à la pénicilline", "حساسية من البنسلين"),
    6: ("Sous anticoagulant (Sintrom)", "يتناول دواء مميّعًا للدم"),
    14: ("Diabétique de type 2", "مريض بالسكري من النوع 2"),
}
NOTES = {0: ("Préfère les rendez-vous le matin.", "يفضّل المواعيد الصباحية."),
         8: ("Vient avec sa mère.", "يأتي مع والدته.")}
#: Indices of patients with a role in the story (see :func:`seed_demo`).
PLAN_PATIENT, FAMILY_PARENT, FAMILY_CHILD = 0, 1, 2
UNRELIABLE = (4, 5)
SERIES_PATIENTS = (7, 8)
TODAY_DONE, TODAY_IN_TREATMENT, TODAY_ARRIVED = 9, 10, (11, 12, 13)
METHODS = ["cash"] * 14 + ["d17"] * 2 + ["card"] * 2 + ["cheque", "transfer"]
TEETH = [f"{q}{n}" for q in (1, 2, 3, 4) for n in range(1, 9)]
TOOTH_SERVICES = {"Soin carie / composite", "Extraction", "Traitement de canal", "Couronne – séance"}
DEPOSIT = 20_000
STEP = timedelta(minutes=15)


@dataclass(frozen=True)
class Svc:
    id: int
    name_fr: str
    name_ar: str
    minutes: int
    price: int


@dataclass
class Plan:
    patient: int
    doctor: int
    svc: Svc
    start: datetime
    status: str = "scheduled"
    source: str = "staff"
    series_id: uuid.UUID | None = None
    deposit: int = 0
    patient_note: str = ""
    id: int | None = None

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.svc.minutes)


@dataclass
class Calendar:
    """Who is busy when – keeps practitioners and patients free of overlaps (like the EXCLUDE constraints)."""

    busy: dict[tuple[str, int], list[tuple[datetime, datetime]]] = field(default_factory=lambda: defaultdict(list))

    def free(self, keys: Iterable[tuple[str, int]], start: datetime, end: datetime) -> bool:
        return all(not (s < end and start < e) for k in keys for s, e in self.busy[k])

    def book(self, plan: Plan) -> None:
        for key in (("d", plan.doctor), ("p", plan.patient)):
            self.busy[key].append((plan.start, plan.end))


def _price(minutes: int) -> int:
    """Invented fees: 1.5 DT per minute rounded to 5 DT, at least 20 DT – whole dinars, in millimes."""
    return max(20, round(minutes * 1.5 / 5) * 5) * 1000


# --- seeding ---------------------------------------------------------------------------------------------------

class DemoSeeder:
    def __init__(self, conn: Connection, now: datetime, lang: str, specialty: str, rng: random.Random) -> None:
        self.conn, self.now, self.lang, self.specialty, self.rng = conn, now, lang, specialty, rng
        self.arabic = lang == "ar"
        self.today = now.astimezone(TUNIS).date()
        self.calendar = Calendar()
        self.plans: list[Plan] = []
        self.used_on: dict[date, set[int]] = defaultdict(set)

    # -- rows -------------------------------------------------------------------------------------------------

    def practice(self) -> int:
        name, name_ar = PRACTICE_NAMES[self.specialty]
        self.practice_id = self.conn.execute(
            insert(practice)
            .values(
                name=name, name_ar=name_ar, slug=demo_slug(), specialty=self.specialty,
                contact_name="Dr. Démo" if not self.arabic else "د. تجربة",
                address="Avenue de la Démo 1", city="Tunis", governorate="tunis", phone="+216 00 000 000",
                is_demo=True, demo_expires_at=self.now + DEMO_TTL, online_booking_enabled=True, created_at=self.now,
            )
            .returning(practice.c.id)
        ).scalar_one()
        insert_default_services(self.conn, self.practice_id, self.specialty)
        rows = self.conn.execute(
            select(service.c.id, service.c.name_fr, service.c.name_ar, service.c.duration_min)
            .where(service.c.practice_id == self.practice_id)
            .order_by(service.c.sort)
        ).all()
        self.services = [Svc(r.id, r.name_fr, r.name_ar, r.duration_min, _price(r.duration_min)) for r in rows]
        for s in self.services:
            self.conn.execute(service.update().where(service.c.id == s.id).values(price_millimes=s.price))
        doctors = PRACTITIONERS.get(self.specialty, DEFAULT_PRACTITIONERS)
        self.doctors = [
            self.conn.execute(
                insert(practitioner)
                .values(practice_id=self.practice_id, title=title, name=doctor, sort=n, created_at=self.now)
                .returning(practitioner.c.id)
            ).scalar_one()
            for n, (title, doctor) in enumerate(doctors, start=1)
        ]
        return self.practice_id

    def owner(self) -> int:
        self.user_id = self.conn.execute(
            insert(app_user)
            .values(
                email=f"demo-{secrets.token_hex(6)}@demo.daftar.invalid",
                password_hash=hash_password(secrets.token_urlsafe(32)),  # nobody knows it: the demo uses its token
                practice_id=self.practice_id, role="owner", name="Dr. Démo" if not self.arabic else "د. تجربة",
                lang=self.lang, created_at=self.now,
            )
            .returning(app_user.c.id)
        ).scalar_one()
        return self.user_id

    def patients(self) -> None:
        rng, rows = self.rng, []
        for i in range(PATIENTS):
            first = (FEMALE if i % 2 == 0 else MALE)[(i // 2) % len(FEMALE if i % 2 == 0 else MALE)]
            last = LAST[FAMILY_PARENT] if i == FAMILY_CHILD else LAST[i]
            phone_no = FAMILY_PARENT + 1 if i == FAMILY_CHILD else i + 1
            child = self.specialty == "pediatre" or i == FAMILY_CHILD
            birth_year = rng.randint(2012, 2025) if child else rng.randint(1950, 2008)
            prefers_fr = i % 5 == 0
            lang = ("fr" if prefers_fr else "ar") if self.arabic else ("ar" if prefers_fr else "fr")
            days_ago = rng.randint(0, 20) if i >= 20 else rng.randint(40, 700)
            pick = 1 if self.arabic else 0
            rows.append({
                "practice_id": self.practice_id, "first_name": first[pick], "last_name": last[pick],
                "phone": f"+21600000{phone_no:03d}", "birth_year": birth_year, "lang": lang,
                "reminder_consent": i % 6 != 5, "notes": NOTES[i][pick] if i in NOTES else "",
                "alerts": ALERTS[i][pick] if i in ALERTS else "", "created_at": self.now - timedelta(days=days_ago),
            })
        result = self.conn.execute(insert(patient).returning(patient.c.id, sort_by_parameter_order=True), rows)
        self.patient_ids = [r.id for r in result]
        self.patient_rows = rows

    # -- calendar ---------------------------------------------------------------------------------------------

    def _windows(self, day: date) -> list[tuple[datetime, datetime]]:
        windows = windows_for(DEFAULT_WEEKLY_HOURS, day)
        if not windows and day == self.today:  # the waiting room of the demo is always busy
            windows = windows_for(DEFAULT_WEEKLY_HOURS, day - timedelta(days=1))
        return [(at_tunis(day, a), at_tunis(day, b)) for a, b in windows]

    def _place(self, plan: Plan) -> bool:
        if not self.calendar.free((("d", plan.doctor), ("p", plan.patient)), plan.start, plan.end):
            return False
        self.calendar.book(plan)
        self.plans.append(plan)
        self.used_on[plan.start.astimezone(TUNIS).date()].add(plan.patient)
        return True

    def _service(self) -> Svc:
        weights = [3 if n < 2 else 1 for n in range(len(self.services))]
        return self.rng.choices(self.services, weights=weights)[0]

    def _open_days(self, offsets: Iterable[int]) -> list[date]:
        days = [self.today + timedelta(days=d) for d in offsets]
        return [d for d in days if windows_for(DEFAULT_WEEKLY_HOURS, d)]

    def story(self) -> None:
        """The appointments every demo must show, placed before the random filling."""
        main, first = self.doctors[0], self.services[0]
        # "now" in the story: the current time, kept inside the morning/afternoon so the waiting room makes sense
        local_now = self.now.astimezone(TUNIS)
        anchor = at_tunis(self.today, min(max(local_now.time(), time(9, 0)), time(14, 30)))
        self.anchor = anchor.replace(minute=anchor.minute - anchor.minute % 5, second=0, microsecond=0)
        start = self.anchor - timedelta(minutes=10)
        minutes = timedelta(minutes=first.minutes)
        self._place(Plan(TODAY_DONE, main, first, start - minutes, "done"))
        self._place(Plan(TODAY_IN_TREATMENT, main, first, start, "in_treatment"))
        for n, who in enumerate(TODAY_ARRIVED, start=1):
            self._place(Plan(who, main, first, start + n * minutes, "arrived"))
        past = self._open_days(range(-13, 0))
        future = self._open_days(range(1, 8))
        for k, who in enumerate(UNRELIABLE):  # two no-shows each → "Acompte conseillé"
            for day in (past[1], past[5]):
                self._place(Plan(who, main, first, at_tunis(day, time(8, 0)) + k * minutes, "no_show"))
        self._place(Plan(UNRELIABLE[0], main, first, at_tunis(future[0], time(8, 0)), "confirmed", deposit=DEPOSIT))
        if self.specialty in ("kinesitherapeute", "psychologue"):
            self._series(SERIES_PATIENTS[0], self.doctors[0], (1, 4), time(10, 0))
            self._series(SERIES_PATIENTS[1], self.doctors[-1], (2, 5), time(15, 0))

    def _series(self, who: int, doctor: int, weekdays: tuple[int, ...], at: time) -> None:
        series_id = uuid.uuid4()
        for offset in range(-14, 8):
            day = self.today + timedelta(days=offset)
            if day.isoweekday() not in weekdays:
                continue
            start = at_tunis(day, at)
            status = "done" if start + timedelta(minutes=self.services[0].minutes) <= self.now else "scheduled"
            self._place(Plan(who, doctor, self.services[0], start, status, series_id=series_id))

    def fill(self) -> None:
        for offset in range(-14, 8):
            day = self.today + timedelta(days=offset)
            if offset < 0:
                rate = 0.55
            elif offset == 0:
                rate = 0.8
            else:
                rate = max(0.15, 0.75 - 0.08 * offset)
            for begin, end in self._windows(day):
                for doctor in self.doctors:
                    self._fill_window(day, doctor, begin, end, rate, offset)

    def _fill_window(self, day: date, doctor: int, begin: datetime, end: datetime, rate: float, offset: int) -> None:
        cursor = begin
        while cursor < end:
            svc = self._service()
            stop = cursor + timedelta(minutes=svc.minutes)
            straddles_now = offset == 0 and cursor < self.anchor < stop
            if stop > end or straddles_now or not self.calendar.free((("d", doctor),), cursor, stop):
                cursor += STEP
                continue
            if self.rng.random() >= rate:
                cursor += STEP
                continue
            who = self._free_patient(day, cursor, stop)
            if who is None:
                cursor += STEP
                continue
            self._place(Plan(who, doctor, svc, cursor, self._status(offset, stop)))
            cursor = stop

    def _free_patient(self, day: date, start: datetime, end: datetime) -> int | None:
        free = [i for i in range(PATIENTS) if self.calendar.free((("p", i),), start, end)]
        fresh = [i for i in free if i not in self.used_on[day]]
        pool = fresh or free
        return self.rng.choice(pool) if pool else None

    def _status(self, offset: int, end: datetime) -> str:
        r = self.rng.random()
        if offset < 0 or (offset == 0 and end <= self.anchor):
            return "cancelled" if r < 0.08 and offset < 0 else "no_show" if r < 0.16 else "done"
        return "cancelled" if r < 0.05 else "confirmed" if r < 0.45 else "scheduled"

    def requests(self) -> None:
        """Three online requests in the coming days (one from a new patient with a note) and a few online bookings."""
        future = [p for p in self.plans if p.start.astimezone(TUNIS).date() > self.today and p.status == "scheduled"
                  and p.series_id is None]
        seen: set[int] = set()
        picked = []
        for plan in sorted(future, key=lambda p: p.start):
            if plan.patient not in seen and len(picked) < 3:
                picked.append(plan)
                seen.add(plan.patient)
        for n, plan in enumerate(picked):
            plan.status, plan.source = "requested", "online"
            if n == 0:
                plan.patient_note = "Première consultation." if not self.arabic else "أول زيارة."
        for plan in [p for p in future if p.status == "scheduled"][-3:]:
            plan.status, plan.source = "confirmed", "online"
        # small demos (one psychologist) could miss a status by chance – every status must be visible
        self._ensure("cancelled", past=True)
        self._ensure("cancelled", past=False)
        self._ensure("confirmed", past=False)

    def _ensure(self, status: str, *, past: bool) -> None:
        def side(plan: Plan) -> bool:
            day = plan.start.astimezone(TUNIS).date()
            return day < self.today if past else day > self.today

        if any(p.status == status and side(p) for p in self.plans):
            return
        source = "done" if past else "scheduled"
        for plan in self.plans:
            if plan.status == source and side(plan) and plan.series_id is None:
                plan.status = status
                return

    def write_appointments(self) -> None:
        rows = []
        for p in self.plans:
            reason = p.svc.name_ar if self.arabic and p.svc.name_ar else p.svc.name_fr
            rows.append({
                "practice_id": self.practice_id, "patient_id": self.patient_ids[p.patient], "practitioner_id": p.doctor,
                "service_id": p.svc.id, "starts_at": p.start, "duration_min": p.svc.minutes, "ends_at": p.end,
                "reason": reason, "status": p.status, "source": p.source, "patient_note": p.patient_note,
                "deposit_required_millimes": p.deposit, "series_id": p.series_id, "created_by": self.user_id,
                "created_at": min(self.now, p.start - timedelta(days=3)),
            })
        result = self.conn.execute(insert(appointment).returning(appointment.c.id, sort_by_parameter_order=True), rows)
        for plan, row in zip(self.plans, result, strict=True):
            plan.id = row.id

    # -- money and waiting room ---------------------------------------------------------------------------------

    def money(self) -> None:
        rng, treatments, payments = self.rng, [], []

        def label(svc: Svc) -> str:
            return svc.name_ar if self.arabic and svc.name_ar else svc.name_fr

        def pay(who: int, amount: int, at: datetime, **extra: Any) -> None:
            payments.append({"practice_id": self.practice_id, "patient_id": self.patient_ids[who],
                             "amount_millimes": amount, "method": rng.choice(METHODS), "paid_at": min(at, self.now),
                             "received_by": self.user_id, "created_at": self.now, "appointment_id": None,
                             "is_deposit": False, "note": "", **extra})

        for p in self.plans:
            if p.status != "done" or (p.patient != TODAY_DONE and rng.random() > 0.85):
                continue
            tooth = rng.choice(TEETH) if self.specialty == "dentiste" and p.svc.name_fr in TOOTH_SERVICES else None
            treatments.append({"practice_id": self.practice_id, "patient_id": self.patient_ids[p.patient],
                               "label": label(p.svc), "tooth": tooth, "price_millimes": p.svc.price,
                               "performed_on": p.start.astimezone(TUNIS).date(), "appointment_id": p.id,
                               "created_at": min(self.now, p.end)})
            r = rng.random()
            if p.patient == TODAY_DONE or r < 0.7:
                pay(p.patient, p.svc.price, p.end, appointment_id=p.id)
            elif r < 0.85:
                pay(p.patient, p.svc.price // 2000 * 1000 or 1000, p.end, appointment_id=p.id, note="Acompte" if not self.arabic else "دفعة")
        # a treatment plan paid in instalments, still open
        if self.specialty == "dentiste":
            plan_label = "تاج خزفي" if self.arabic else "Couronne céramique"
            price, tooth = 450_000, "26"
        else:
            plan_label, price, tooth = label(self.services[0]) + " ×4", self.services[0].price * 4, None
        performed = self.today - timedelta(days=7)
        treatments.append({"practice_id": self.practice_id, "patient_id": self.patient_ids[PLAN_PATIENT],
                           "label": plan_label, "tooth": tooth, "price_millimes": price, "performed_on": performed,
                           "appointment_id": None, "created_at": self.now - timedelta(days=7)})
        instalment = price // 3 // 1000 * 1000
        pay(PLAN_PATIENT, instalment, self.now - timedelta(days=7), note="1er versement" if not self.arabic else "القسط الأول")
        pay(PLAN_PATIENT, instalment, self.now - timedelta(days=1), note="2e versement" if not self.arabic else "القسط الثاني")
        # the deposit of the unreliable patient's next appointment
        deposit_plan = next(p for p in self.plans if p.deposit)
        pay(UNRELIABLE[0], DEPOSIT, self.now - timedelta(hours=2), appointment_id=deposit_plan.id, is_deposit=True,
            note="Acompte" if not self.arabic else "تسبقة")
        self.conn.execute(insert(treatment), treatments)
        self.conn.execute(insert(payment), payments)

    def waiting_room(self) -> None:
        entries = []
        for p in self.plans:
            if p.start.astimezone(TUNIS).date() != self.today or p.status not in ("done", "in_treatment", "arrived"):
                continue
            row = self.patient_rows[p.patient]
            entry = {"practice_id": self.practice_id, "day": self.today, "patient_id": self.patient_ids[p.patient],
                     "appointment_id": p.id, "name": f"{row['first_name']} {row['last_name']}", "phone": row["phone"]}
            if p.status == "done":
                entry.update(status="done", arrived_at=p.start - timedelta(minutes=10), called_at=p.start, done_at=p.end)
            elif p.status == "in_treatment":
                entry.update(status="in_treatment", arrived_at=p.start - timedelta(minutes=15), called_at=p.start)
            else:
                waited = 20 - 7 * TODAY_ARRIVED.index(p.patient) if p.patient in TODAY_ARRIVED else 5
                entry.update(status="waiting", arrived_at=self.anchor - timedelta(minutes=waited))
            entry["arrived_at"] = min(entry["arrived_at"], self.now)
            entries.append(entry)
        entries.sort(key=lambda e: e["arrived_at"])
        for n, entry in enumerate(entries, start=1):
            entry.setdefault("called_at", None)
            entry.setdefault("done_at", None)
            entry["ticket_no"] = n
        if entries:
            self.conn.execute(insert(queue_entry), entries)


def seed_demo(conn: Connection, *, now: datetime, lang: str, specialty: str, rng: random.Random | None = None) -> int:
    """Creates a filled demo practice and its owner; returns the owner's user id."""
    seeder = DemoSeeder(conn, now, lang, specialty, rng or random.Random(secrets.randbits(64)))
    seeder.practice()
    seeder.owner()
    seeder.patients()
    seeder.story()
    seeder.fill()
    seeder.requests()
    seeder.write_appointments()
    seeder.money()
    seeder.waiting_room()
    return seeder.user_id


@router.post("", status_code=201)
def start_demo(ctx: Ctx, conn: Conn, ip: ClientIp, body: Annotated[DemoIn | None, Body()] = None) -> Session:
    body = body or DemoIn()
    everyone = ctx.limiter("demo-global", GLOBAL_PER_DAY, timedelta(days=1))
    if not everyone.allowed():
        raise too_many_requests(TOO_MANY, retry_after=everyone.retry_after())
    ctx.limiter("demo-ip", PER_IP, timedelta(hours=1)).enforce(ip, TOO_MANY)
    everyone.enforce("", TOO_MANY)
    user_id = seed_demo(conn, now=ctx.clock.now(), lang=body.lang, specialty=body.specialty)
    ctx.metrics.demo_started.inc()
    return session_for(ctx, conn, user_id)


def delete_expired_demos(conn: Connection, now: datetime) -> int:
    """Deletes demo practices whose 24 h are over – everything in them goes with them (ON DELETE CASCADE)."""
    result = conn.execute(delete(practice).where(practice.c.is_demo.is_(True), practice.c.demo_expires_at < now))
    return result.rowcount or 0


def cleanup_demos(ctx: AppContext) -> None:
    with ctx.engine.begin() as conn:
        delete_expired_demos(conn, ctx.clock.now())

