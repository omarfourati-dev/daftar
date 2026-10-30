"""``/api/practice``: the practice's own settings (sections 5, 11.2, 12, 13, 15).

- ``GET /api/practice`` (every staff role) → :class:`PracticeOut` – everything except the admin fields
  (``adminNotes``); ``slug``, ``status``, ``planCode`` and ``paidUntil`` are shown read-only.
- ``PATCH /api/practice`` (owner) – partial update of :class:`PracticePatch`; ``slug``, ``status``, ``paidUntil``,
  ``planCode`` and ``adminNotes`` are ignored (only the admin changes them, ``/api/admin/practices/{id}``).
- ``POST /api/practice/display-token`` (owner) → ``{displayToken}``: a new link for the waiting-room screen; the old
  one stops working at once.

Reusable for the admin module: :class:`PracticeFields` (validated input fields), :func:`practice_columns`
(API fields → table columns) and :func:`practice_out` (row → output).
"""

from __future__ import annotations

import secrets
from datetime import date
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter
from pydantic import AfterValidator, BeforeValidator, Field, StrictBool, model_validator
from sqlalchemy import Connection, Row, select, update

from .catalog import Specialty
from .deps import Conn, OwnerWriter, StaffUser
from .hours import WeeklyHours, agenda_range
from .phone import OptionalPhone, Phone
from .problems import not_found
from .schemas import ApiModel, Email, Name, TunisDateTime
from .tables import practice
from .tunisia import GOVERNORATES

router = APIRouter(prefix="/api/practice", tags=["practice"])


# --- field types ------------------------------------------------------------------------------------------------


def _governorate(value: str) -> str:
    if value not in GOVERNORATES:
        raise ValueError("validation: Gouvernorat inconnu.")
    return value


def _empty_to_none(value: Any) -> Any:
    return None if isinstance(value, str) and not value.strip() else value


def _lower(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


Governorate = Annotated[str, AfterValidator(_governorate)]
OptionalEmail = Annotated[Email | None, BeforeValidator(_empty_to_none), AfterValidator(lambda v: v and v.lower())]
#: ``#rrggbb`` (upper case is accepted and stored lower case).
BrandColor = Annotated[str, BeforeValidator(_lower), Field(pattern=r"^#[0-9a-f]{6}$")]
#: Empty or an ``https://`` link (shown on the public booking page – never ``javascript:`` or plain http).
MapsUrl = Annotated[str, Field(max_length=500, pattern=r"^(?:https://\S+)?$")]
SlotMinutes = Literal[5, 10, 15, 20, 30, 60]
DurationMin = Annotated[int, Field(ge=5, le=480)]
ShortText = Annotated[str, Field(max_length=120)]


class OnlineBooking(ApiModel):
    enabled: bool
    auto_confirm: bool
    horizon_days: int
    min_notice_hours: int
    max_per_day: int
    block_no_shows: int


class OnlineBookingPatch(ApiModel):
    enabled: StrictBool | None = None
    auto_confirm: StrictBool | None = None
    horizon_days: Annotated[int, Field(ge=1, le=365)] | None = None
    min_notice_hours: Annotated[int, Field(ge=0, le=168)] | None = None
    max_per_day: Annotated[int, Field(ge=1, le=500)] | None = None
    block_no_shows: Annotated[int, Field(ge=0, le=20)] | None = None


#: onlineBooking.<field> → practice column
BOOKING_COLUMNS = {
    "enabled": "online_booking_enabled",
    "auto_confirm": "online_auto_confirm",
    "horizon_days": "booking_horizon_days",
    "min_notice_hours": "booking_min_notice_hours",
    "max_per_day": "booking_max_per_day",
    "block_no_shows": "booking_block_no_shows",
}
#: Fields that may be cleared with ``null``.
NULLABLE = frozenset({"whatsapp", "email", "governorate"})


class PracticeFields(ApiModel):
    """The practice data an owner may change (all optional – a PATCH). ``null`` only clears the nullable ones."""

    name: Name | None = None
    name_ar: ShortText | None = None
    specialty: Specialty | None = None
    contact_name: ShortText | None = None
    phone: Phone | None = None
    whatsapp: OptionalPhone = None
    email: OptionalEmail = None
    address: Annotated[str, Field(max_length=300)] | None = None
    postal_code: Annotated[str, Field(max_length=10)] | None = None
    city: ShortText | None = None
    governorate: Governorate | None = None
    maps_url: MapsUrl | None = None
    description_fr: Annotated[str, Field(max_length=2000)] | None = None
    description_ar: Annotated[str, Field(max_length=2000)] | None = None
    tax_id: Annotated[str, Field(max_length=40)] | None = None
    brand_color: BrandColor | None = None
    weekly_hours: WeeklyHours | None = None
    slot_minutes: SlotMinutes | None = None
    default_duration_min: DurationMin | None = None
    reminder_template_fr: Annotated[str, Field(max_length=1000)] | None = None
    reminder_template_ar: Annotated[str, Field(max_length=1000)] | None = None
    online_booking: OnlineBookingPatch | None = None

    #: Fields that may be cleared with ``null`` (subclasses extend it).
    nullable_fields: ClassVar[frozenset[str]] = NULLABLE

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> PracticeFields:
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable_fields:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


class PracticePatch(PracticeFields):
    pass


def practice_columns(body: PracticeFields) -> dict[str, Any]:
    """The table columns a (partial) input sets – ``onlineBooking`` flattened into its columns."""
    values = body.model_dump(exclude_unset=True, by_alias=False)
    booking = values.pop("online_booking", None) or {}
    for key, value in booking.items():
        if value is not None:
            values[BOOKING_COLUMNS[key]] = value
    return values


class PracticeOut(ApiModel):
    id: int
    name: str
    name_ar: str
    slug: str
    specialty: str
    contact_name: str
    phone: str
    whatsapp: str | None
    email: str | None
    address: str
    postal_code: str
    city: str
    governorate: str | None
    maps_url: str
    description_fr: str
    description_ar: str
    tax_id: str
    brand_color: str
    weekly_hours: dict[str, list[list[str]]]
    #: Earliest opening and latest closing of the week (the agenda range), "HH:MM" or null when never open.
    day_start: str | None
    day_end: str | None
    slot_minutes: int
    default_duration_min: int
    reminder_template_fr: str
    reminder_template_ar: str
    display_token: str
    is_demo: bool
    demo_expires_at: TunisDateTime | None
    status: str
    plan_code: str
    paid_until: date | None
    online_booking: OnlineBooking
    created_at: TunisDateTime


def _hours(row: Row[Any]) -> dict[str, list[list[str]]]:
    return {str(d): [list(w) for w in row.weekly_hours.get(str(d), [])] for d in range(1, 8)}


def practice_values(row: Row[Any]) -> dict[str, Any]:
    """The common output fields of a practice row (also used by the admin view)."""
    hours = _hours(row)
    day_range = agenda_range(hours)
    return {
        **{name: getattr(row, name) for name in PracticeOut.model_fields if hasattr(row, name)},
        "weekly_hours": hours,
        "day_start": day_range[0].strftime("%H:%M") if day_range else None,
        "day_end": day_range[1].strftime("%H:%M") if day_range else None,
        "online_booking": OnlineBooking(**{key: getattr(row, col) for key, col in BOOKING_COLUMNS.items()}),
    }


def practice_out(row: Row[Any]) -> PracticeOut:
    return PracticeOut(**practice_values(row))


def load_practice(conn: Connection, practice_id: int) -> Row[Any]:
    row = conn.execute(select(practice).where(practice.c.id == practice_id)).first()
    if row is None:
        raise not_found()
    return row


class DisplayTokenOut(ApiModel):
    display_token: str


@router.get("")
def get_practice(user: StaffUser, conn: Conn) -> PracticeOut:
    return practice_out(load_practice(conn, user.pid))


@router.patch("")
def patch_practice(body: PracticePatch, user: OwnerWriter, conn: Conn) -> PracticeOut:
    values = practice_columns(body)
    if values:
        conn.execute(update(practice).where(practice.c.id == user.pid).values(**values))
    return practice_out(load_practice(conn, user.pid))


@router.post("/display-token")
def new_display_token(user: OwnerWriter, conn: Conn) -> DisplayTokenOut:
    token = secrets.token_hex(16)
    conn.execute(update(practice).where(practice.c.id == user.pid).values(display_token=token))
    return DisplayTokenOut(display_token=token)

