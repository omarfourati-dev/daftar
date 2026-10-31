"""Invitations: one-time links ``/invitation#<token>`` (the token lives in the URL fragment, never in a server log).

Only the SHA-256 of a token is stored. Public endpoints (the invited person has no account yet):
- ``POST /api/invitations/preview {token}`` → ``{practiceName, role, isDemo}``; 404 when invalid, expired or used;
- ``POST /api/invitations/accept {token, name, email, password, lang?}`` → 201 ``{token, user}``; 409 e-mail taken;
  403 ``demo_invitation`` for an invitation of a demo practice (security review M2: the demo shows how a link is
  made, but nobody gets an account there – checked before the e-mail, so no "e-mail taken" oracle).

Accepting creates the account in the invitation's practice with the invitation's role.
Both endpoints together allow 5 attempts per IP and 15 minutes; only an accepted invitation clears the counter (a
valid preview does not – security review M2: alternating "accept" and "preview" probed e-mails without limit).

Reusable for the staff and admin modules: :func:`create_invitation` (returns the clear token exactly once).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import Connection, delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from .auth import Session, session_for
from .context import AppContext
from .deps import ClientIp, Conn, Ctx
from .passwords import hash_password, password_problem
from .problems import conflict, forbidden, not_found, too_many_requests, unprocessable
from .schemas import ApiModel, Email, Lang, Name, PracticeRole
from .tables import app_user, invitation, practice

router = APIRouter(prefix="/api/invitations", tags=["invitations"])

INVITATION_TTL = timedelta(days=7)
#: Unused, expired invitations are deleted this long after they expired (see daftar/jobs.py).
KEEP_EXPIRED = timedelta(days=30)
INVALID = "Cette invitation n'est pas valide, a expiré ou a déjà été utilisée."
DEMO = ("Cette invitation vient d'une démo : elle montre comment inviter votre équipe, mais aucun compte n'est créé. "
        "Dans votre cabinet, la personne invitée crée ici son compte.")
TOO_MANY = "Trop de tentatives. Veuillez réessayer dans 15 minutes."


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    """256 random bits, URL-safe (43 characters)."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class CreatedInvitation:
    id: int
    token: str  # shown once, never stored
    expires_at: datetime


def create_invitation(
    conn: Connection, *, practice_id: int, role: PracticeRole, created_by: int | None, now: datetime
) -> CreatedInvitation:
    """Stores a new invitation (hash only) and returns the clear token for the link ``/invitation#<token>``."""
    token = new_token()
    expires_at = now + INVITATION_TTL
    new_id = conn.execute(
        insert(invitation)
        .values(
            practice_id=practice_id,
            role=role,
            token_hash=hash_token(token),
            created_by=created_by,
            created_at=now,
            expires_at=expires_at,
        )
        .returning(invitation.c.id)
    ).scalar_one()
    return CreatedInvitation(id=new_id, token=token, expires_at=expires_at)


def delete_stale_invitations(conn: Connection, now: datetime) -> int:
    """Removes unused invitations that expired more than 30 days ago. Returns the number deleted."""
    result = conn.execute(
        delete(invitation).where(invitation.c.used_at.is_(None), invitation.c.expires_at < now - KEEP_EXPIRED)
    )
    return result.rowcount or 0


class TokenIn(ApiModel):
    token: str = Field(max_length=200)


class PreviewOut(ApiModel):
    practice_name: str
    role: PracticeRole
    is_demo: bool


class AcceptIn(ApiModel):
    token: str = Field(max_length=200)
    name: Name
    email: Email
    password: str = Field(max_length=1000)
    lang: Lang = "fr"


def _reserve(ctx: AppContext, ip: str) -> None:
    if not ctx.login_throttle.reserve_key(f"invitation:{ip}"):
        raise too_many_requests(TOO_MANY)


def _open_invitation(conn: Connection, token: str, now: datetime, *, lock: bool = False):  # type: ignore[no-untyped-def]
    query = (
        select(invitation.c.id, invitation.c.role, invitation.c.practice_id, practice.c.name.label("practice_name"),
               practice.c.is_demo)
        .select_from(invitation.join(practice, practice.c.id == invitation.c.practice_id))
        .where(
            invitation.c.token_hash == hash_token(token),
            invitation.c.used_at.is_(None),
            invitation.c.expires_at > now,
        )
    )
    if lock:
        query = query.with_for_update(of=invitation)
    return conn.execute(query).first()


@router.post("/preview")
def preview(body: TokenIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> PreviewOut:
    _reserve(ctx, ip)
    row = _open_invitation(conn, body.token, ctx.clock.now())
    if row is None:
        raise not_found(INVALID, code="invitation_invalid")
    return PreviewOut(practice_name=row.practice_name, role=row.role, is_demo=row.is_demo)


@router.post("/accept", status_code=201)
def accept(body: AcceptIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> Session:
    if problem := password_problem(body.password):
        raise unprocessable(problem[1], code=problem[0])
    _reserve(ctx, ip)
    now = ctx.clock.now()
    # FOR UPDATE: the same link cannot create two accounts, even with two clicks at once.
    row = _open_invitation(conn, body.token, now, lock=True)
    if row is None:
        raise not_found(INVALID, code="invitation_invalid")
    if row.is_demo:
        raise forbidden(DEMO, code="demo_invitation")
    email = body.email.lower()
    taken = conn.execute(select(app_user.c.id).where(app_user.c.email == email)).first()
    if taken is not None:
        raise conflict("Un compte existe déjà avec cette adresse e-mail.", code="email_taken")
    try:
        user_id = conn.execute(
            insert(app_user)
            .values(
                email=email,
                password_hash=hash_password(body.password),
                practice_id=row.practice_id,
                role=row.role,
                name=body.name,
                lang=body.lang,
                created_at=now,
            )
            .returning(app_user.c.id)
        ).scalar_one()
    except IntegrityError as exc:  # a parallel request took the e-mail meanwhile
        raise conflict("Un compte existe déjà avec cette adresse e-mail.", code="email_taken") from exc
    conn.execute(update(invitation).where(invitation.c.id == row.id).values(used_at=now))
    ctx.login_throttle.clear_key(f"invitation:{ip}")
    return session_for(ctx, conn, user_id)
