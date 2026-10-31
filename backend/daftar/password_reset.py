"""Password reset without e-mail (backlog A3, section 15): one-time links ``/reinitialiser#<token>``, valid 24 h.

The owner makes a link for a team member (``POST /api/staff/{id}/reset-link``), the admin one for an owner
(``POST /api/admin/practices/{id}/owner-reset-link``) – both through :func:`create_reset_link`. Only the SHA-256 of
the token is stored; a new link replaces the open links of that account.

Public:
- ``POST /api/password-reset/preview {token}`` → ``{email, practiceName}``; 404 ``reset_invalid``;
- ``POST /api/password-reset/accept {token, password}`` → ``{token, user}``: new password, every old session ends
  (``token_version`` + 1), the link is used up. 5 wrong tokens per IP and 15 minutes, then 429.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import Connection, delete, insert, select, update

from .auth import Session, session_for
from .context import AppContext
from .deps import ClientIp, Conn, Ctx
from .invitations import hash_token, new_token
from .passwords import hash_password, password_problem
from .problems import not_found, too_many_requests, unprocessable
from .schemas import ApiModel, TunisDateTime
from .tables import app_user, password_reset, practice

router = APIRouter(prefix="/api/password-reset", tags=["password-reset"])

RESET_TTL = timedelta(hours=24)
INVALID = "Ce lien n'est pas valide, a expiré ou a déjà été utilisé."
TOO_MANY = "Trop de tentatives. Veuillez réessayer dans 15 minutes."


@dataclass(frozen=True)
class CreatedResetLink:
    token: str  # shown once, never stored
    expires_at: datetime


class ResetLinkOut(ApiModel):
    token: str
    expires_at: TunisDateTime


def create_reset_link(conn: Connection, *, user_id: int, created_by: int | None, now: datetime) -> CreatedResetLink:
    """Stores a new link for ``user_id`` (hash only) and removes the open ones made before."""
    conn.execute(delete(password_reset).where(password_reset.c.user_id == user_id, password_reset.c.used_at.is_(None)))
    token = new_token()
    expires_at = now + RESET_TTL
    conn.execute(
        insert(password_reset).values(
            user_id=user_id, token_hash=hash_token(token), created_by=created_by, created_at=now, expires_at=expires_at
        )
    )
    return CreatedResetLink(token=token, expires_at=expires_at)


class TokenIn(ApiModel):
    token: str = Field(max_length=200)


class AcceptIn(ApiModel):
    token: str = Field(max_length=200)
    password: str = Field(max_length=1000)


class PreviewOut(ApiModel):
    email: str
    practice_name: str


def _reserve(ctx: AppContext, ip: str) -> None:
    if not ctx.login_throttle.reserve_key(f"password-reset:{ip}"):
        raise too_many_requests(TOO_MANY)


def _open_link(conn: Connection, token: str, now: datetime, *, lock: bool = False):  # type: ignore[no-untyped-def]
    query = (
        select(password_reset.c.id, password_reset.c.user_id, app_user.c.email, practice.c.name.label("practice_name"))
        .select_from(
            password_reset.join(app_user, app_user.c.id == password_reset.c.user_id).outerjoin(
                practice, practice.c.id == app_user.c.practice_id
            )
        )
        .where(
            password_reset.c.token_hash == hash_token(token),
            password_reset.c.used_at.is_(None),
            password_reset.c.expires_at > now,
        )
    )
    if lock:
        query = query.with_for_update(of=password_reset)
    return conn.execute(query).first()


@router.post("/preview")
def preview(body: TokenIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> PreviewOut:
    _reserve(ctx, ip)
    row = _open_link(conn, body.token, ctx.clock.now())
    if row is None:
        raise not_found(INVALID, code="reset_invalid")
    ctx.login_throttle.clear_key(f"password-reset:{ip}")
    return PreviewOut(email=row.email, practice_name=row.practice_name or "")


@router.post("/accept")
def accept(body: AcceptIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> Session:
    if problem := password_problem(body.password):
        raise unprocessable(problem[1], code=problem[0])
    _reserve(ctx, ip)
    now = ctx.clock.now()
    row = _open_link(conn, body.token, now, lock=True)  # FOR UPDATE: two clicks cannot use one link twice
    if row is None:
        raise not_found(INVALID, code="reset_invalid")
    if problem := password_problem(body.password, row.email):  # now that the account is known
        raise unprocessable(problem[1], code=problem[0])
    conn.execute(
        update(app_user)
        .where(app_user.c.id == row.user_id)
        .values(password_hash=hash_password(body.password), token_version=app_user.c.token_version + 1)
    )
    conn.execute(update(password_reset).where(password_reset.c.id == row.id).values(used_at=now))
    ctx.login_throttle.clear_key(f"password-reset:{ip}")
    return session_for(ctx, conn, row.user_id)
