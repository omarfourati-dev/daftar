"""“Erste Schritte” – the getting-started checklist on the dashboard (backlog A5, section 15).

``GET /api/onboarding`` (every staff role) → ``{steps: [{key, done}], dismissed}``, keys in this order:

| key | done when |
|---|---|
| hours | the opening hours were saved (owner settings or admin wizard) or differ from the defaults |
| services | an active service has a price |
| practitioners | an active practitioner exists |
| team | another account exists in the practice or a staff invitation was made |
| booking | online booking is switched on |
| import | an import was committed, or ticked by hand |
| install, poster | ticked by hand: ``POST /api/onboarding/{key}/done`` |

``POST /api/onboarding/dismiss`` hides the checklist (what is done stays done). Both POSTs: staff, not suspended.
The state lives in ``practice.onboarding`` (JSONB): ``{"hours": true, "install": true, "dismissed": true, …}``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from sqlalchemy import Connection, and_, exists, func, select, update

from .deps import Conn, StaffUser, StaffWriter
from .hours import DEFAULT_WEEKLY_HOURS, validate_weekly_hours
from .problems import unprocessable
from .schemas import ApiModel
from .tables import app_user, import_job, invitation, practice, practitioner, service

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

StepKey = Literal["hours", "services", "practitioners", "team", "booking", "import", "install", "poster"]
KEYS: tuple[StepKey, ...] = ("hours", "services", "practitioners", "team", "booking", "import", "install", "poster")
#: Steps a user may tick; the others follow the data.
MANUAL = frozenset({"import", "install", "poster"})


class Step(ApiModel):
    key: StepKey
    done: bool


class OnboardingOut(ApiModel):
    steps: list[Step]
    dismissed: bool


def flag(key: str) -> Any:
    """``onboarding || {key: true}`` – use as value in an ``update(practice)``: ``values(onboarding=flag("hours"))``."""
    return practice.c.onboarding.op("||")(func.jsonb_build_object(key, True))


def _changed_hours(weekly_hours: Any) -> bool:
    try:
        return validate_weekly_hours(weekly_hours) != DEFAULT_WEEKLY_HOURS
    except ValueError:  # hand-edited JSON in the database – somebody set hours
        return True


def _state(conn: Connection, practice_id: int) -> OnboardingOut:
    pid = practice_id
    row = conn.execute(
        select(
            practice.c.onboarding,
            practice.c.weekly_hours,
            practice.c.online_booking_enabled,
            exists().where(service.c.practice_id == pid, service.c.active, service.c.price_millimes.is_not(None)).label("services"),
            exists().where(practitioner.c.practice_id == pid, practitioner.c.active).label("practitioners"),
            (
                exists().where(app_user.c.practice_id == pid, app_user.c.role != "owner")
                | exists().where(and_(invitation.c.practice_id == pid, invitation.c.role != "owner"))
            ).label("team"),
            exists().where(import_job.c.practice_id == pid, import_job.c.committed_at.is_not(None)).label("imported"),
        ).where(practice.c.id == pid)
    ).one()
    flags = row.onboarding or {}
    done = {
        "hours": bool(flags.get("hours")) or _changed_hours(row.weekly_hours),
        "services": row.services,
        "practitioners": row.practitioners,
        "team": row.team,
        "booking": row.online_booking_enabled,
        "import": bool(flags.get("import")) or row.imported,
        "install": bool(flags.get("install")),
        "poster": bool(flags.get("poster")),
    }
    return OnboardingOut(steps=[Step(key=k, done=bool(done[k])) for k in KEYS], dismissed=bool(flags.get("dismissed")))


@router.get("")
def get_onboarding(user: StaffUser, conn: Conn) -> OnboardingOut:
    return _state(conn, user.pid)


@router.post("/dismiss")
def dismiss(user: StaffWriter, conn: Conn) -> OnboardingOut:
    conn.execute(update(practice).where(practice.c.id == user.pid).values(onboarding=flag("dismissed")))
    return _state(conn, user.pid)


@router.post("/{key}/done")
def mark_done(key: StepKey, user: StaffWriter, conn: Conn) -> OnboardingOut:
    if key not in MANUAL:
        raise unprocessable("Cette étape se coche toute seule quand elle est faite.", code="onboarding_derived")
    conn.execute(update(practice).where(practice.c.id == user.pid).values(onboarding=flag(key)))
    return _state(conn, user.pid)
