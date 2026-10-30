"""Online booking for patients (section 11.3, backlog C1) – public, without login, never other patients' data.

Practice pages (``/r/<slug>`` and ``https://<slug>.<BASE_DOMAIN>``); suspended or canceled practices are 404:
- ``GET /api/public/practices/{slug}`` → public profile: names, address, contact, map, description, opening hours,
  ``onlineBookingEnabled``, ``horizonDays``, ``minNoticeHours``, online-bookable active services and practitioners
- ``GET /api/public/practices/{slug}/slots?date=&serviceId=&practitionerId=`` → ``{date, slots: ["09:00", …]}`` –
  the staff rules (grid, hours, closures, booked times) plus the minimum notice, the horizon (Tunis days from today)
  and ``booking_max_per_day`` online bookings a day; 404 ``booking_disabled``; 422 ``invalid_service`` /
  ``invalid_practitioner``
- ``POST /api/public/practices/{slug}/bookings {serviceId, practitionerId?, startsAt, firstName, lastName, phone, lang,
  reminderConsent, note?, website}`` → 201 ``{status: requested|confirmed, startsAt, endsAt, serviceName,
  practitionerName, manageToken}``. The patient is recognized by phone **and** last name (case-insensitive), else
  created. 409 ``slot_unavailable``; 422 ``too_soon`` / ``outside_horizon`` / ``blocked`` (this phone number has
  ``booking_block_no_shows`` no-shows in the practice); 429 ``booking_limit`` (2 future online bookings per phone),
  ``day_full`` (``booking_max_per_day``), ``too_many_requests`` (20 attempts per IP and hour – patients behind a
  carrier's NAT share one –, 3 attempts per phone number and practice and hour). Bookings of one practice run one
  after the other (``pg_advisory_xact_lock``), so parallel requests cannot pass both limits. ``website`` is a
  honeypot: when filled, the answer looks like a success and nothing is stored.

The patient's link ``/rdv#<manageToken>`` (only the SHA-256 is stored; in the fragment the token never reaches a
server log):
- ``POST /api/public/bookings/lookup {token}`` → ``{status, startsAt, endsAt, serviceName, practitionerName,
  canCancel, cancelUntil, practice: {…contact}}`` – no names, no phone of the patient
- ``POST /api/public/bookings/cancel {token}`` → the same, cancelled; 409 ``too_late`` (less than
  ``booking_min_notice_hours`` before), 409 ``cannot_cancel`` (already arrived, done, no-show)
- for now also with the token in the path (old links ``/rdv/<token>``): ``GET /api/public/bookings/{token}``,
  ``POST /api/public/bookings/{token}/cancel`` – same answers
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import Field, StrictBool
from sqlalchemy import Connection, Row, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import scheduling
from .clock import TUNIS, tunis_day_bounds
from .context import AppContext
from .db import constraint_name
from .deps import ClientIp, Conn, Ctx
from .hosts import CLOSED_STATUSES
from .invitations import hash_token, new_token
from .phone import Phone
from .problems import ApiError, conflict, not_found, unprocessable
from .scheduling import StartsAt, load_calendar, local_day
from .schemas import ApiModel, Lang, Name, TunisDateTime
from .slugs import slug_problem
from .tables import FREEING_STATUSES, appointment, patient, practice, practitioner, service

router = APIRouter(prefix="/api/public", tags=["public"])

#: Profile and slot requests per IP and 10 minutes (a patient flips through days).
READ_LIMIT = 300
READ_WINDOW = timedelta(minutes=10)
#: Booking attempts per IP and hour (section 11.3; fixlist 2: many patients share a carrier's NAT address).
BOOKING_LIMIT = 20
BOOKING_WINDOW = timedelta(hours=1)
#: Booking attempts per phone number and practice and hour.
PHONE_LIMIT = 3
PHONE_WINDOW = timedelta(hours=1)
#: First key of ``pg_advisory_xact_lock(key, practice_id)``: the online bookings of one practice, one after the other.
BOOKING_LOCK = 0x0B00C
#: Views and cancellations of booking links per IP and 10 minutes.
MANAGE_LIMIT = 60
MANAGE_WINDOW = timedelta(minutes=10)
#: Future online bookings one phone number may hold in one practice.
MAX_FUTURE_PER_PHONE = 2
OPEN = ("requested", "scheduled", "confirmed")


# --- models -------------------------------------------------------------------------------------------------------


class PublicService(ApiModel):
    id: int
    name_fr: str
    name_ar: str
    duration_min: int
    price_millimes: int | None


class PublicPractitioner(ApiModel):
    id: int
    name: str
    title: str
    specialty: str | None


class PublicPractice(ApiModel):
    slug: str
    name: str
    name_ar: str
    specialty: str
    brand_color: str
    address: str
    postal_code: str
    city: str
    governorate: str | None
    phone: str
    whatsapp: str | None
    maps_url: str
    description_fr: str
    description_ar: str
    weekly_hours: dict[str, list[list[str]]]
    online_booking_enabled: bool
    horizon_days: int
    min_notice_hours: int
    services: list[PublicService]
    practitioners: list[PublicPractitioner]


class SlotsOut(ApiModel):
    date: date
    slots: list[str]


class BookingIn(ApiModel):
    service_id: int
    practitioner_id: int | None = None
    starts_at: StartsAt
    first_name: Name
    last_name: Name
    phone: Phone
    lang: Lang = "fr"
    reminder_consent: StrictBool = False
    note: Annotated[str, Field(max_length=1000)] = ""
    #: Honeypot – people never see this field; bots fill it.
    website: Annotated[str, Field(max_length=500)] = ""


class BookingCreated(ApiModel):
    status: Literal["requested", "confirmed"]
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    service_name: str
    practitioner_name: str | None
    manage_token: str


class PracticeContact(ApiModel):
    slug: str
    name: str
    name_ar: str
    phone: str
    whatsapp: str | None
    address: str
    city: str
    maps_url: str


class TokenIn(ApiModel):
    token: Annotated[str, Field(min_length=1, max_length=200)]


class BookingView(ApiModel):
    status: str
    starts_at: TunisDateTime
    ends_at: TunisDateTime
    service_name: str | None
    practitioner_name: str | None
    can_cancel: bool
    cancel_until: TunisDateTime
    practice: PracticeContact


# --- helpers ------------------------------------------------------------------------------------------------------


def _limit(ctx: AppContext, name: str, limit: int, window: timedelta, ip: str) -> None:
    ctx.limiter(name, limit, window).enforce(ip)


def _practice(conn: Connection, slug: str) -> Row[Any]:
    if slug_problem(slug) is not None:
        raise not_found()
    row = conn.execute(select(practice).where(practice.c.slug == slug)).first()
    if row is None or row.status in CLOSED_STATUSES:
        raise not_found()
    return row


def _bookable(row: Row[Any]) -> None:
    if not row.online_booking_enabled:
        raise not_found("Ce cabinet ne prend pas de rendez-vous en ligne.", code="booking_disabled")


def _service(conn: Connection, practice_id: int, service_id: int) -> Row[Any]:
    row = conn.execute(
        select(service.c.id, service.c.name_fr, service.c.duration_min).where(
            service.c.id == service_id, service.c.practice_id == practice_id, service.c.active, service.c.online_bookable
        )
    ).first()
    if row is None:
        raise unprocessable("Cet acte ne se réserve pas en ligne.", code="invalid_service")
    return row


def _resources(conn: Connection, practice_id: int, practitioner_id: int | None) -> list[int | None]:
    """The calendars a patient may book: the chosen practitioner, else every online one, else the practice's one
    calendar when it has no practitioner at all."""
    bookable = conn.execute(
        select(practitioner.c.id)
        .where(practitioner.c.practice_id == practice_id, practitioner.c.active, practitioner.c.online_bookable)
        .order_by(practitioner.c.sort, practitioner.c.id)
    ).scalars().all()
    if practitioner_id is not None:
        if practitioner_id not in bookable:
            raise unprocessable("Ce praticien ne se réserve pas en ligne.", code="invalid_practitioner")
        return [practitioner_id]
    if bookable:
        return list(bookable)
    any_active = conn.execute(
        select(practitioner.c.id).where(practitioner.c.practice_id == practice_id, practitioner.c.active).limit(1)
    ).first()
    return [] if any_active else [None]


def _online_that_day(conn: Connection, practice_id: int, day: date) -> int:
    start, end = tunis_day_bounds(day)
    return conn.execute(
        select(func.count()).where(
            appointment.c.practice_id == practice_id,
            appointment.c.source == "online",
            appointment.c.status.notin_(FREEING_STATUSES),
            appointment.c.starts_at >= start,
            appointment.c.starts_at < end,
        )
    ).scalar_one()


def _window(row: Row[Any], now: datetime) -> tuple[datetime, date]:
    """(earliest start, last day) a patient may book."""
    return now + timedelta(hours=row.booking_min_notice_hours), local_day(now) + timedelta(days=row.booking_horizon_days)


def _free(
    conn: Connection, row: Row[Any], day: date, duration: int, resources: list[int | None], now: datetime,
    patient_id: int | None = None,
) -> list[tuple[datetime, list[int | None]]]:
    earliest, last_day = _window(row, now)
    if day < local_day(now) or day > last_day or not resources:
        return []
    if _online_that_day(conn, row.id, day) >= row.booking_max_per_day:
        return []
    return scheduling.free_starts(conn, load_calendar(conn, row.id), day, duration, resources, not_before=earliest,
                                  patient_id=patient_id)


def _one_at_a_time(conn: Connection, practice_id: int) -> None:
    """Waits until no other online booking of this practice is running (released when the transaction ends) – so the
    limits per phone and per day hold for parallel requests too."""
    conn.execute(select(func.pg_advisory_xact_lock(BOOKING_LOCK, practice_id)))


def _slot_taken() -> ApiError:
    return conflict("Ce créneau n'est plus disponible. Choisissez un autre horaire.", code="slot_unavailable")


# --- practice pages -------------------------------------------------------------------------------------------------


@router.get("/practices/{slug}")
def profile(slug: str, ctx: Ctx, conn: Conn, ip: ClientIp) -> PublicPractice:
    _limit(ctx, "booking-read", READ_LIMIT, READ_WINDOW, ip)
    row = _practice(conn, slug)
    services = conn.execute(
        select(service.c.id, service.c.name_fr, service.c.name_ar, service.c.duration_min, service.c.price_millimes)
        .where(service.c.practice_id == row.id, service.c.active, service.c.online_bookable)
        .order_by(service.c.sort, service.c.id)
    ).all()
    doctors = conn.execute(
        select(practitioner.c.id, practitioner.c.name, practitioner.c.title, practitioner.c.specialty)
        .where(practitioner.c.practice_id == row.id, practitioner.c.active, practitioner.c.online_bookable)
        .order_by(practitioner.c.sort, practitioner.c.id)
    ).all()
    copied = ("slug", "name", "name_ar", "specialty", "brand_color", "address", "postal_code", "city", "governorate",
              "phone", "whatsapp", "maps_url", "description_fr", "description_ar", "online_booking_enabled")
    return PublicPractice(
        **{k: getattr(row, k) for k in copied},
        weekly_hours={str(d): row.weekly_hours.get(str(d), []) for d in range(1, 8)},
        horizon_days=row.booking_horizon_days,
        min_notice_hours=row.booking_min_notice_hours,
        services=[PublicService.model_validate(s, from_attributes=True) for s in services],
        practitioners=[PublicPractitioner.model_validate(d, from_attributes=True) for d in doctors],
    )


@router.get("/practices/{slug}/slots")
def slots(
    slug: str,
    ctx: Ctx,
    conn: Conn,
    ip: ClientIp,
    date_: Annotated[date, Query(alias="date")],
    service_id: Annotated[int, Query(alias="serviceId")],
    practitioner_id: Annotated[int | None, Query(alias="practitionerId")] = None,
) -> SlotsOut:
    _limit(ctx, "booking-read", READ_LIMIT, READ_WINDOW, ip)
    row = _practice(conn, slug)
    _bookable(row)
    svc = _service(conn, row.id, service_id)
    resources = _resources(conn, row.id, practitioner_id)
    found = _free(conn, row, date_, svc.duration_min, resources, ctx.clock.now())
    return SlotsOut(date=date_, slots=[t.astimezone(TUNIS).strftime("%H:%M") for t, _ in found])


@router.post("/practices/{slug}/bookings", status_code=201)
def create_booking(slug: str, body: BookingIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> BookingCreated:
    _limit(ctx, "booking-ip", BOOKING_LIMIT, BOOKING_WINDOW, ip)
    row = _practice(conn, slug)
    if body.website:  # a bot: answer like a success, store nothing
        return BookingCreated(status="requested", starts_at=body.starts_at, ends_at=body.starts_at + timedelta(minutes=30),
                              service_name="", practitioner_name=None, manage_token=new_token())
    _bookable(row)
    ctx.limiter("booking-phone", PHONE_LIMIT, PHONE_WINDOW).enforce(
        f"{row.id}:{body.phone}", "Trop de tentatives pour ce numéro. Réessayez plus tard ou appelez le cabinet."
    )
    svc = _service(conn, row.id, body.service_id)
    resources = _resources(conn, row.id, body.practitioner_id)
    now = ctx.clock.now()
    earliest, last_day = _window(row, now)
    day = local_day(body.starts_at)
    if body.starts_at < earliest:
        raise unprocessable("Ce créneau est trop proche. Appelez le cabinet.", code="too_soon")
    if day > last_day:
        raise unprocessable("Cette date est trop lointaine pour une réservation en ligne.", code="outside_horizon")
    _one_at_a_time(conn, row.id)
    same_phone = select(patient.c.id).where(patient.c.practice_id == row.id, patient.c.phone == body.phone)
    if row.booking_block_no_shows > 0:
        no_shows = conn.execute(
            select(func.count()).where(appointment.c.patient_id.in_(same_phone.scalar_subquery()),
                                       appointment.c.status == "no_show")
        ).scalar_one()
        if no_shows >= row.booking_block_no_shows:
            raise unprocessable("Merci d'appeler le cabinet pour prendre rendez-vous.", code="blocked")
    future = conn.execute(
        select(func.count()).where(
            appointment.c.patient_id.in_(same_phone.scalar_subquery()),
            appointment.c.source == "online",
            appointment.c.status.notin_(FREEING_STATUSES),
            appointment.c.starts_at > now,
        )
    ).scalar_one()
    if future >= MAX_FUTURE_PER_PHONE:
        raise ApiError(429, "Vous avez déjà des rendez-vous à venir. Appelez le cabinet.", code="booking_limit")
    if _online_that_day(conn, row.id, day) >= row.booking_max_per_day:
        raise ApiError(429, "Plus de réservations en ligne ce jour-là. Appelez le cabinet.", code="day_full")
    known = conn.execute(
        select(patient.c.id)
        .where(patient.c.practice_id == row.id, patient.c.phone == body.phone,
               func.lower(func.btrim(patient.c.last_name)) == body.last_name.strip().lower())
        .order_by(patient.c.id)
        .limit(1)
    ).scalar()
    free = dict(_free(conn, row, day, svc.duration_min, resources, now, patient_id=known))
    chosen = free.get(body.starts_at)
    if not chosen:
        raise _slot_taken()
    doctor = chosen[0]
    patient_id = known or conn.execute(
        insert(patient)
        .values(practice_id=row.id, first_name=body.first_name, last_name=body.last_name, phone=body.phone,
                lang=body.lang, reminder_consent=body.reminder_consent, created_at=now)
        .returning(patient.c.id)
    ).scalar_one()
    token = new_token()
    ends_at = body.starts_at + timedelta(minutes=svc.duration_min)
    status = "confirmed" if row.online_auto_confirm else "requested"
    try:
        with conn.begin_nested():
            conn.execute(
                insert(appointment).values(
                    practice_id=row.id, patient_id=patient_id, practitioner_id=doctor, service_id=svc.id,
                    starts_at=body.starts_at, duration_min=svc.duration_min, ends_at=ends_at, reason=svc.name_fr,
                    status=status, source="online", patient_note=body.note, booking_token_hash=hash_token(token),
                    created_at=now,
                )
            )
    except IntegrityError as exc:  # taken in the same instant by somebody else
        if constraint_name(exc) not in scheduling.OVERLAP_CONSTRAINTS:
            raise
        raise _slot_taken() from exc
    ctx.metrics.appointments_created.labels("online").inc()
    doctor_name = None
    if doctor is not None:
        doctor_name = conn.execute(select(practitioner.c.name).where(practitioner.c.id == doctor)).scalar_one()
    return BookingCreated(status=status, starts_at=body.starts_at, ends_at=ends_at, service_name=svc.name_fr,
                          practitioner_name=doctor_name, manage_token=token)


# --- the patient's link ---------------------------------------------------------------------------------------------


def _booking(conn: Connection, token: str, *, lock: bool = False) -> Row[Any]:
    query = (
        select(
            appointment.c.id, appointment.c.status, appointment.c.starts_at, appointment.c.ends_at,
            service.c.name_fr.label("service_name"), practitioner.c.name.label("practitioner_name"),
            practice.c.slug, practice.c.name, practice.c.name_ar, practice.c.phone, practice.c.whatsapp,
            practice.c.address, practice.c.city, practice.c.maps_url, practice.c.booking_min_notice_hours,
        )
        .select_from(
            appointment.join(practice, practice.c.id == appointment.c.practice_id)
            .outerjoin(service, service.c.id == appointment.c.service_id)
            .outerjoin(practitioner, practitioner.c.id == appointment.c.practitioner_id)
        )
        .where(appointment.c.booking_token_hash == hash_token(token))
    )
    if lock:
        query = query.with_for_update(of=appointment)
    row = conn.execute(query).first()
    if row is None:
        raise not_found()
    return row


def _view(row: Row[Any], now: datetime, status: str | None = None) -> BookingView:
    current = status or row.status
    cancel_until = row.starts_at - timedelta(hours=row.booking_min_notice_hours)
    return BookingView(
        status=current, starts_at=row.starts_at, ends_at=row.ends_at, service_name=row.service_name,
        practitioner_name=row.practitioner_name, can_cancel=current in OPEN and now <= cancel_until,
        cancel_until=cancel_until,
        practice=PracticeContact(slug=row.slug, name=row.name, name_ar=row.name_ar, phone=row.phone,
                                 whatsapp=row.whatsapp, address=row.address, city=row.city, maps_url=row.maps_url),
    )


@router.post("/bookings/lookup")
def lookup_booking(body: TokenIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> BookingView:
    return view_booking(body.token, ctx, conn, ip)


@router.post("/bookings/cancel")
def cancel_booking_by_body(body: TokenIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> BookingView:
    return cancel_booking(body.token, ctx, conn, ip)


@router.get("/bookings/{token}")
def view_booking(token: str, ctx: Ctx, conn: Conn, ip: ClientIp) -> BookingView:
    _limit(ctx, "booking-manage", MANAGE_LIMIT, MANAGE_WINDOW, ip)
    return _view(_booking(conn, token), ctx.clock.now())


@router.post("/bookings/{token}/cancel")
def cancel_booking(token: str, ctx: Ctx, conn: Conn, ip: ClientIp) -> BookingView:
    _limit(ctx, "booking-manage", MANAGE_LIMIT, MANAGE_WINDOW, ip)
    row = _booking(conn, token, lock=True)
    now = ctx.clock.now()
    if row.status == "cancelled":
        return _view(row, now)
    if row.status not in OPEN:
        raise conflict("Ce rendez-vous ne peut plus être annulé en ligne.", code="cannot_cancel")
    if now > row.starts_at - timedelta(hours=row.booking_min_notice_hours):
        raise conflict("Il est trop tard pour annuler en ligne. Merci d'appeler le cabinet.", code="too_late")
    conn.execute(update(appointment).where(appointment.c.id == row.id).values(status="cancelled"))
    return _view(row, now, status="cancelled")
