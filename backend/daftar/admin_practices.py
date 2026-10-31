"""Admin customer master (sections 11.2, 12, 15; backlog A1): practices with complete data.

All endpoints: admin only (403 for practice staff, 401 without token).
- ``GET /api/admin/practices?demo=false`` → ``[AdminPracticeListItem]`` newest first; demos only with ``demo=true``
- ``POST /api/admin/practices`` → 201 ``{practice: AdminPractice, invitation: {token, expiresAt}}`` (owner link);
  ``services`` missing → the default catalog of the specialty; slug lower-cased, 422 ``slug_invalid``/
  ``slug_reserved`` (also ``demo-…``, kept for demo practices), 409 ``slug_taken``; 422 ``invalid_plan``
- ``GET/PATCH/DELETE /api/admin/practices/{id}`` – PATCH changes everything incl. slug, status, plan, paid until
  (``paidUntil``, alias ``pilotUntil``) and admin notes; practitioners and services are managed by the owner
- ``POST /api/admin/practices/{id}/invitation`` → 201 ``{token, expiresAt}`` (new owner link, 7 days)
- ``POST /api/admin/practices/{id}/owner-reset-link`` → 201 ``{token, expiresAt}`` (24 h); 404 ``owner_missing``
- ``GET /api/admin/slug-available?slug=&practiceId=`` → ``{available, reason: invalid|reserved|taken|null}``
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter, Query, Response
from pydantic import AliasChoices, Field, StrictBool
from sqlalchemy import Connection, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .catalog import Specialty, insert_default_services
from .db import constraint_name
from .deps import AdminUser, Conn, Ctx
from .invitations import create_invitation
from .money import Millimes
from .password_reset import ResetLinkOut, create_reset_link
from .phone import OptionalPhone, Phone
from .hours import WeeklyHours
from .practice_settings import (
    BOOKING_COLUMNS,
    NULLABLE,
    BrandColor,
    DurationMin,
    Governorate,
    MapsUrl,
    OptionalEmail,
    PracticeFields,
    PracticeOut,
    ShortText,
    SlotMinutes,
    load_practice,
    practice_columns,
    practice_values,
)
from .practitioners import PractitionerOut, Title
from .problems import conflict, not_found, unprocessable
from .schemas import ApiModel, Name, TunisDateTime
from .services import NameAr, ServiceOut
from .slugs import slug_problem
from .tables import app_user, appointment, patient, payment, plan, practice, practitioner, queue_entry, service

router = APIRouter(prefix="/api/admin", tags=["admin"])

PracticeStatus = Literal["pilot", "trial", "active", "past_due", "suspended", "canceled"]
LongText = Annotated[str, Field(max_length=2000)]
AdminNotes = Annotated[str, Field(max_length=5000)]
#: ``paidUntil`` (section 11.4) – ``pilotUntil`` (section 11.2) is accepted as the same field.
PAID_UNTIL = AliasChoices("paidUntil", "pilotUntil", "paid_until")
DEMO_PREFIX = "demo-"


# --- input ------------------------------------------------------------------------------------------------------


class AdminPractitionerIn(ApiModel):
    name: Name
    title: Title = "Dr."
    specialty: Specialty | None = None
    color: BrandColor = "#0f766e"
    online_bookable: StrictBool = True


class AdminServiceIn(ApiModel):
    name_fr: Name
    name_ar: NameAr = ""
    duration_min: DurationMin
    price_millimes: Millimes | None = None
    online_bookable: StrictBool = False
    color: BrandColor | None = None


class OnlineBookingIn(ApiModel):
    enabled: StrictBool = False
    auto_confirm: StrictBool = False
    horizon_days: Annotated[int, Field(ge=1, le=365)] = 30
    min_notice_hours: Annotated[int, Field(ge=0, le=168)] = 2
    max_per_day: Annotated[int, Field(ge=1, le=500)] = 20
    block_no_shows: Annotated[int, Field(ge=0, le=20)] = 2


class AdminPracticeIn(ApiModel):
    name: Name
    name_ar: ShortText = ""
    slug: Annotated[str, Field(max_length=100)]
    specialty: Specialty
    contact_name: Name
    phone: Phone
    whatsapp: OptionalPhone = None
    email: OptionalEmail = None
    address: Annotated[str, Field(min_length=1, max_length=300)]
    postal_code: Annotated[str, Field(max_length=10)] = ""
    city: Name
    governorate: Governorate
    maps_url: MapsUrl = ""
    description_fr: LongText = ""
    description_ar: LongText = ""
    tax_id: Annotated[str, Field(max_length=40)] = ""
    brand_color: BrandColor = "#0f766e"
    status: PracticeStatus = "pilot"
    paid_until: date | None = Field(default=None, validation_alias=PAID_UNTIL)
    plan_code: Annotated[str, Field(max_length=40)] = "pilot"
    admin_notes: AdminNotes = ""
    weekly_hours: WeeklyHours | None = None
    slot_minutes: SlotMinutes = 15
    default_duration_min: DurationMin = 30
    practitioners: Annotated[list[AdminPractitionerIn], Field(max_length=50)] = []
    services: Annotated[list[AdminServiceIn], Field(max_length=100)] | None = None
    online_booking: OnlineBookingIn = OnlineBookingIn()


class AdminPracticePatch(PracticeFields):
    nullable_fields: ClassVar[frozenset[str]] = NULLABLE | {"paid_until"}

    slug: Annotated[str, Field(max_length=100)] | None = None
    status: PracticeStatus | None = None
    paid_until: date | None = Field(default=None, validation_alias=PAID_UNTIL)
    plan_code: Annotated[str, Field(max_length=40)] | None = None
    admin_notes: AdminNotes | None = None


# --- output -----------------------------------------------------------------------------------------------------


class OwnerBrief(ApiModel):
    id: int
    name: str
    email: str


class AdminPracticeOut(PracticeOut):
    admin_notes: str
    #: The same as ``paidUntil`` (end of the pilot or of the paid period) – section 11.2 calls it pilotUntil.
    pilot_until: date | None
    booking_url: str
    users: int
    patients: int
    appointments: int
    owner: OwnerBrief | None
    practitioners: list[PractitionerOut]
    services: list[ServiceOut]


class AdminPracticeListItem(ApiModel):
    id: int
    name: str
    slug: str
    city: str
    governorate: str | None
    specialty: str
    status: str
    plan_code: str
    paid_until: date | None
    is_demo: bool
    created_at: TunisDateTime
    users: int
    patients: int
    appointments: int
    #: Appointments created in the last 7 days – how much the practice really uses Daftar.
    appointments_week: int
    last_activity_at: TunisDateTime | None


class InvitationLinkOut(ApiModel):
    token: str
    expires_at: TunisDateTime


class CreatedPracticeOut(ApiModel):
    practice: AdminPracticeOut
    invitation: InvitationLinkOut


class SlugAvailableOut(ApiModel):
    available: bool
    reason: Literal["invalid", "reserved", "taken"] | None = None


# --- helpers ----------------------------------------------------------------------------------------------------


def slug_reason(conn: Connection, slug: str, except_id: int | None = None) -> Literal["invalid", "reserved", "taken"] | None:
    problem = slug_problem(slug)
    if problem == "invalid":
        return "invalid"
    if problem == "reserved" or slug.startswith(DEMO_PREFIX):
        return "reserved"
    query = select(practice.c.id).where(practice.c.slug == slug)
    if except_id is not None:
        query = query.where(practice.c.id != except_id)
    return "taken" if conn.execute(query).first() is not None else None


def _checked_slug(conn: Connection, raw: str, except_id: int | None = None) -> str:
    slug = raw.strip().lower()
    reason = slug_reason(conn, slug, except_id)
    if reason == "invalid":
        raise unprocessable("Sous-domaine invalide (3 à 40 lettres minuscules, chiffres, tirets).", code="slug_invalid")
    if reason == "reserved":
        raise unprocessable("Ce sous-domaine est réservé.", code="slug_reserved")
    if reason == "taken":
        raise _slug_taken()
    return slug


def _slug_taken() -> Exception:
    return conflict("Ce sous-domaine est déjà utilisé.", code="slug_taken")


def _check_plan(conn: Connection, code: str) -> None:
    if conn.execute(select(plan.c.code).where(plan.c.code == code)).first() is None:
        raise unprocessable("Formule inconnue.", code="invalid_plan")


def _write(conn: Connection, statement: Any) -> Any:
    """Runs an insert/update of a practice; a slug taken meanwhile (unique index) is the same 409."""
    try:
        with conn.begin_nested():
            return conn.execute(statement)
    except IntegrityError as exc:
        if constraint_name(exc) == "practice_slug_key":
            raise _slug_taken() from exc
        raise


def _count(table: Any, *where: Any) -> Any:
    return select(func.count()).select_from(table).where(table.c.practice_id == practice.c.id, *where).scalar_subquery()


def _last(column: Any) -> Any:
    return select(func.max(column)).where(column.table.c.practice_id == practice.c.id).scalar_subquery()


def _usage(now: datetime) -> list[Any]:
    return [
        _count(app_user).label("users"),
        _count(patient).label("patients"),
        _count(appointment).label("appointments"),
        _count(appointment, appointment.c.created_at >= now - timedelta(days=7)).label("appointments_week"),
        func.greatest(
            _last(appointment.c.created_at), _last(patient.c.created_at), _last(payment.c.created_at),
            _last(queue_entry.c.arrived_at),
        ).label("last_activity_at"),
    ]


def admin_practice_out(conn: Connection, ctx_now: datetime, base_domain: str, practice_id: int) -> AdminPracticeOut:
    row = load_practice(conn, practice_id)
    usage = conn.execute(select(*_usage(ctx_now)).where(practice.c.id == practice_id)).one()
    owner = conn.execute(
        select(app_user.c.id, app_user.c.name, app_user.c.email)
        .where(app_user.c.practice_id == practice_id, app_user.c.role == "owner")
        .order_by(app_user.c.id)
        .limit(1)
    ).first()
    doctors = conn.execute(
        select(practitioner).where(practitioner.c.practice_id == practice_id).order_by(practitioner.c.sort, practitioner.c.id)
    ).all()
    catalog = conn.execute(
        select(service).where(service.c.practice_id == practice_id).order_by(service.c.sort, service.c.id)
    ).all()
    return AdminPracticeOut(
        **practice_values(row),
        admin_notes=row.admin_notes,
        pilot_until=row.paid_until,
        booking_url=f"https://{row.slug}.{base_domain}",
        users=usage.users,
        patients=usage.patients,
        appointments=usage.appointments,
        owner=OwnerBrief.model_validate(owner, from_attributes=True) if owner else None,
        practitioners=[PractitionerOut.model_validate(r, from_attributes=True) for r in doctors],
        services=[ServiceOut.model_validate(r, from_attributes=True) for r in catalog],
    )


def _exists(conn: Connection, practice_id: int) -> None:
    if conn.execute(select(practice.c.id).where(practice.c.id == practice_id)).first() is None:
        raise not_found()


# --- endpoints --------------------------------------------------------------------------------------------------


@router.get("/practices")
def list_practices(user: AdminUser, ctx: Ctx, conn: Conn, demo: bool = False) -> list[AdminPracticeListItem]:
    query = select(
        practice.c.id, practice.c.name, practice.c.slug, practice.c.city, practice.c.governorate, practice.c.specialty,
        practice.c.status, practice.c.plan_code, practice.c.paid_until, practice.c.is_demo, practice.c.created_at,
        *_usage(ctx.clock.now()),
    )
    if not demo:
        query = query.where(practice.c.is_demo.is_(False))
    rows = conn.execute(query.order_by(practice.c.created_at.desc(), practice.c.id.desc())).all()
    return [AdminPracticeListItem.model_validate(r, from_attributes=True) for r in rows]


@router.post("/practices", status_code=201)
def create_practice(body: AdminPracticeIn, user: AdminUser, ctx: Ctx, conn: Conn) -> CreatedPracticeOut:
    slug = _checked_slug(conn, body.slug)
    _check_plan(conn, body.plan_code)
    values = body.model_dump(by_alias=False, exclude={"slug", "practitioners", "services", "online_booking"}, exclude_none=False)
    if values["weekly_hours"] is None:
        del values["weekly_hours"]  # the database default (Monday–Saturday with a lunch break)
    else:
        values["onboarding"] = {"hours": True}  # the admin wizard asked for them
    booking = body.online_booking.model_dump(by_alias=False)
    values.update({column: booking[key] for key, column in BOOKING_COLUMNS.items()})
    now = ctx.clock.now()
    practice_id = _write(
        conn, insert(practice).values(**values, slug=slug, created_at=now).returning(practice.c.id)
    ).scalar_one()
    for n, doctor in enumerate(body.practitioners, start=1):
        conn.execute(insert(practitioner).values(practice_id=practice_id, sort=n, created_at=now, **doctor.model_dump(by_alias=False)))
    if body.services is None:
        insert_default_services(conn, practice_id, body.specialty)
    else:
        for n, item in enumerate(body.services, start=1):
            conn.execute(insert(service).values(practice_id=practice_id, sort=n, created_at=now, **item.model_dump(by_alias=False)))
    link = create_invitation(conn, practice_id=practice_id, role="owner", created_by=user.user_id, now=now)
    return CreatedPracticeOut(
        practice=admin_practice_out(conn, now, ctx.settings.base_domain, practice_id),
        invitation=InvitationLinkOut(token=link.token, expires_at=link.expires_at),
    )


@router.get("/slug-available")
def slug_available(
    user: AdminUser, conn: Conn, slug: str = "", practice_id: Annotated[int | None, Query(alias="practiceId")] = None
) -> SlugAvailableOut:
    reason = slug_reason(conn, slug.strip().lower(), practice_id)
    return SlugAvailableOut(available=reason is None, reason=reason)


@router.get("/practices/{practice_id}")
def get_practice(practice_id: int, user: AdminUser, ctx: Ctx, conn: Conn) -> AdminPracticeOut:
    return admin_practice_out(conn, ctx.clock.now(), ctx.settings.base_domain, practice_id)


@router.patch("/practices/{practice_id}")
def patch_practice(practice_id: int, body: AdminPracticePatch, user: AdminUser, ctx: Ctx, conn: Conn) -> AdminPracticeOut:
    _exists(conn, practice_id)
    values = practice_columns(body)
    if "slug" in values:
        values["slug"] = _checked_slug(conn, values["slug"], except_id=practice_id)
    if "plan_code" in values:
        _check_plan(conn, values["plan_code"])
    if values:
        _write(conn, update(practice).where(practice.c.id == practice_id).values(**values))
    return admin_practice_out(conn, ctx.clock.now(), ctx.settings.base_domain, practice_id)


@router.delete("/practices/{practice_id}", status_code=204)
def delete_practice(practice_id: int, user: AdminUser, conn: Conn) -> Response:
    if not conn.execute(delete(practice).where(practice.c.id == practice_id)).rowcount:
        raise not_found()
    return Response(status_code=204)


@router.post("/practices/{practice_id}/invitation", status_code=201)
def owner_invitation(practice_id: int, user: AdminUser, ctx: Ctx, conn: Conn) -> InvitationLinkOut:
    _exists(conn, practice_id)
    link = create_invitation(conn, practice_id=practice_id, role="owner", created_by=user.user_id, now=ctx.clock.now())
    return InvitationLinkOut(token=link.token, expires_at=link.expires_at)


@router.post("/practices/{practice_id}/owner-reset-link", status_code=201)
def owner_reset_link(practice_id: int, user: AdminUser, ctx: Ctx, conn: Conn) -> ResetLinkOut:
    _exists(conn, practice_id)
    owner_id = conn.execute(
        select(app_user.c.id)
        .where(app_user.c.practice_id == practice_id, app_user.c.role == "owner")
        .order_by(app_user.c.id)
        .limit(1)
    ).scalar()
    if owner_id is None:
        raise not_found("Ce cabinet n'a pas encore de titulaire.", code="owner_missing")
    link = create_reset_link(conn, user_id=owner_id, created_by=user.user_id, now=ctx.clock.now())
    return ResetLinkOut(token=link.token, expires_at=link.expires_at)
