"""FastAPI dependencies for every router. Import the ``Annotated`` aliases and use them as parameter types::

    @router.get("/api/patients/{patient_id}")
    def get_patient(patient_id: int, user: StaffUser, conn: Conn) -> PatientOut:
        row = conn.execute(select(patient).where(patient.c.id == patient_id,
                                                 patient.c.practice_id == user.pid)).first()
        if row is None:
            raise not_found()          # also for IDs of another practice – never 403
        ...

- ``Ctx``        the per-app services (settings, clock, metrics, limiters, tokens)
- ``Conn``       a SQLAlchemy connection inside a transaction; commit when the handler returns, rollback on error
- ``ClientIp``   the real client IP (last ``X-Forwarded-For`` entry, set by Caddy)
- ``CurrentUser`` any signed-in account (401 problem otherwise)
- ``StaffUser``  owner, dentist or assistant – has a practice (``user.pid``); use it for reading
- ``StaffWriter`` like StaffUser, but 402 ``subscription_suspended`` when the practice is suspended – use it for
  every endpoint that creates, changes or deletes business data
- ``OwnerUser``  owner only · ``PractitionerUser`` owner or dentist · ``AdminUser`` admin only (403 otherwise)
- ``require_roles("owner", "dentist")`` for other combinations
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Connection, select

from .clock import Clock
from .context import AppContext
from .problems import ApiError, forbidden, unauthorized
from .schemas import Lang, Role
from .tables import app_user, practice


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]


def get_clock(ctx: Ctx) -> Clock:
    return ctx.clock


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_conn(ctx: Ctx) -> Iterator[Connection]:
    with ctx.engine.begin() as conn:
        yield conn


#: One connection and transaction per request (shared by all dependencies of the request), committed before the
#: response is sent (``scope="function"``).
Conn = Annotated[Connection, Depends(get_conn, scope="function")]


def client_ip(request: Request) -> str:
    """Behind Caddy the real client IP is the **last** ``X-Forwarded-For`` entry; earlier ones are client-controlled."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


ClientIp = Annotated[str, Depends(client_ip)]


@dataclass(frozen=True)
class Principal:
    """The signed-in account, re-read from the database on every request (role changes apply immediately)."""

    user_id: int
    email: str
    name: str
    role: Role
    practice_id: int | None
    lang: Lang
    token_version: int
    is_demo: bool = False
    demo_expires_at: datetime | None = None
    #: Subscription status of the practice (pilot, trial, active, past_due, suspended, canceled); None for the admin.
    practice_status: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def pid(self) -> int:
        """The practice id; 403 for the admin (who has none). Use it in every tenant filter."""
        if self.practice_id is None:
            raise forbidden()
        return self.practice_id


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def current_user(request: Request, ctx: Ctx, conn: Conn) -> Principal:
    token = _bearer(request)
    claims = ctx.tokens.verify(token) if token else None
    if claims is None:
        raise unauthorized()
    row = conn.execute(
        select(
            app_user.c.id,
            app_user.c.email,
            app_user.c.name,
            app_user.c.role,
            app_user.c.practice_id,
            app_user.c.lang,
            app_user.c.token_version,
            practice.c.is_demo,
            practice.c.demo_expires_at,
            practice.c.status.label("practice_status"),
        )
        .select_from(app_user.outerjoin(practice, practice.c.id == app_user.c.practice_id))
        .where(app_user.c.id == claims.user_id)
    ).first()
    if row is None or row.token_version != claims.token_version:
        raise unauthorized()
    if row.is_demo and row.demo_expires_at is not None and row.demo_expires_at <= ctx.clock.now():
        raise unauthorized("La démo est terminée.", code="demo_expired")
    return Principal(
        user_id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        practice_id=row.practice_id,
        lang=row.lang,
        token_version=row.token_version,
        is_demo=bool(row.is_demo),
        demo_expires_at=row.demo_expires_at,
        practice_status=row.practice_status,
    )


CurrentUser = Annotated[Principal, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[[Principal], Principal]:
    """Dependency factory: ``Annotated[Principal, Depends(require_roles("owner", "dentist"))]`` → 403 for others."""
    allowed = frozenset(roles)

    def check(user: CurrentUser) -> Principal:
        if user.role not in allowed:
            raise forbidden()
        return user

    check.__name__ = "require_" + "_".join(roles)
    return check


StaffUser = Annotated[Principal, Depends(require_roles("owner", "dentist", "assistant"))]


def require_writable(user: StaffUser) -> Principal:
    """Staff of a practice whose subscription is not suspended (section 11.4) – else 402."""
    if user.practice_status == "suspended":
        raise ApiError(402, "Abonnement suspendu.", code="subscription_suspended")
    return user


#: For every endpoint that changes business data (create, update, delete): staff + subscription not suspended.
StaffWriter = Annotated[Principal, Depends(require_writable)]
PractitionerUser = Annotated[Principal, Depends(require_roles("owner", "dentist"))]
OwnerUser = Annotated[Principal, Depends(require_roles("owner"))]
AdminUser = Annotated[Principal, Depends(require_roles("admin"))]
