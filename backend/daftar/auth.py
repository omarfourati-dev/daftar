"""``/api/auth/*``: login, own account, password, log out everywhere.

Reusable for other modules:
- :func:`load_me` – the ``Me`` object of a user id;
- :func:`session_for` – ``{token, user}`` for a freshly created or authenticated user (login, invitation, demo).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import Field
from sqlalchemy import Connection, select, update

from .context import AppContext
from .deps import ClientIp, Conn, Ctx, CurrentUser
from .hosts import APP_LABEL, practice_by_slug, subdomain_label
from .passwords import hash_password, needs_rehash, password_problem, verify_against_dummy, verify_password
from .problems import bad_request, too_many_requests, unauthorized, unprocessable
from .schemas import ApiModel, Lang, Name, Role, TunisDateTime
from .tables import app_user, practice

router = APIRouter(prefix="/api/auth", tags=["auth"])

TOO_MANY = "Trop de tentatives. Veuillez réessayer dans 15 minutes."


class PracticeBrief(ApiModel):
    id: int
    name: str
    slug: str
    specialty: str
    status: str
    brand_color: str
    is_demo: bool
    demo_expires_at: TunisDateTime | None = None


class Me(ApiModel):
    id: int
    email: str
    name: str
    role: Role
    lang: Lang
    practice: PracticeBrief | None = None


class Session(ApiModel):
    token: str
    user: Me


class TokenOut(ApiModel):
    token: str


class LoginIn(ApiModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1000)


class MePatch(ApiModel):
    name: Name | None = None
    lang: Lang | None = None


class PasswordIn(ApiModel):
    current: str = Field(max_length=1000)
    next: str = Field(max_length=1000)


def load_me(conn: Connection, user_id: int) -> Me:
    row = conn.execute(
        select(
            app_user.c.id,
            app_user.c.email,
            app_user.c.name,
            app_user.c.role,
            app_user.c.lang,
            practice.c.id.label("practice_id"),
            practice.c.name.label("practice_name"),
            practice.c.slug,
            practice.c.specialty,
            practice.c.status,
            practice.c.brand_color,
            practice.c.is_demo,
            practice.c.demo_expires_at,
        )
        .select_from(app_user.outerjoin(practice, practice.c.id == app_user.c.practice_id))
        .where(app_user.c.id == user_id)
    ).one()
    brief = None
    if row.practice_id is not None:
        brief = PracticeBrief(
            id=row.practice_id,
            name=row.practice_name,
            slug=row.slug,
            specialty=row.specialty,
            status=row.status,
            brand_color=row.brand_color,
            is_demo=row.is_demo,
            demo_expires_at=row.demo_expires_at,
        )
    return Me(id=row.id, email=row.email, name=row.name, role=row.role, lang=row.lang, practice=brief)


def issue_token(ctx: AppContext, conn: Connection, user_id: int) -> str:
    version = conn.execute(select(app_user.c.token_version).where(app_user.c.id == user_id)).scalar_one()
    return ctx.tokens.issue(user_id, version)


def session_for(ctx: AppContext, conn: Connection, user_id: int) -> Session:
    """``{token, user}`` – the answer of login, invitation accept and demo start."""
    return Session(token=issue_token(ctx, conn, user_id), user=load_me(conn, user_id))


def bump_token_version(conn: Connection, user_id: int) -> None:
    """Invalidates every token issued so far for this user."""
    conn.execute(update(app_user).where(app_user.c.id == user_id).values(token_version=app_user.c.token_version + 1))


@router.post("/login")
def login(body: LoginIn, request: Request, ctx: Ctx, conn: Conn, ip: ClientIp) -> Session:
    """Signing in works on the app host ``app.<BASE_DOMAIN>`` (admin and every practice's staff) and on a practice's
    own sub-domain (only its staff) – never on the main domain, which shows ads (fixlist 1). Everybody else gets
    exactly the answer of a wrong password."""
    email = body.email.strip().lower()
    if not ctx.login_throttle.reserve(email, ip):
        ctx.metrics.logins.labels("throttled").inc()
        raise too_many_requests(TOO_MANY)
    if ctx.login_throttle.account_locked(email):  # 10 failures of this e-mail from anywhere (security review M4)
        ctx.metrics.logins.labels("throttled").inc()
        raise too_many_requests(TOO_MANY, retry_after=ctx.login_throttle.account_retry_after(email))
    row = conn.execute(
        select(app_user.c.id, app_user.c.password_hash, app_user.c.practice_id).where(app_user.c.email == email)
    ).first()
    if row is None:
        verify_against_dummy(body.password)  # same duration for unknown e-mails
        ok = False
    else:
        ok = verify_password(body.password, row.password_hash)
    label = subdomain_label(request.headers.get("host"), ctx.settings.base_domain)
    if ok and label != APP_LABEL:
        host_practice = practice_by_slug(conn, label) if label is not None else None
        ok = host_practice is not None and row is not None and row.practice_id == host_practice.id
    if not ok:
        ctx.metrics.logins.labels("failed").inc()
        ctx.login_throttle.failure(email)
        raise unauthorized("E-mail ou mot de passe incorrect.", code="invalid_credentials")
    ctx.login_throttle.success(email, ip)
    ctx.metrics.logins.labels("ok").inc()
    if needs_rehash(row.password_hash):  # parameters were raised since the hash was made
        conn.execute(update(app_user).where(app_user.c.id == row.id).values(password_hash=hash_password(body.password)))
    return session_for(ctx, conn, row.id)


@router.get("/me")
def get_me(user: CurrentUser, conn: Conn) -> Me:
    return load_me(conn, user.user_id)


@router.patch("/me")
def patch_me(body: MePatch, user: CurrentUser, conn: Conn) -> Me:
    values = body.model_dump(exclude_none=True, by_alias=False)
    if values:
        conn.execute(update(app_user).where(app_user.c.id == user.user_id).values(**values))
    return load_me(conn, user.user_id)


@router.post("/password")
def change_password(body: PasswordIn, user: CurrentUser, ctx: Ctx, conn: Conn) -> TokenOut:
    key = f"password:{user.user_id}"
    if not ctx.login_throttle.reserve_key(key):
        raise too_many_requests(TOO_MANY)
    current_hash = conn.execute(select(app_user.c.password_hash).where(app_user.c.id == user.user_id)).scalar_one()
    if not verify_password(body.current, current_hash):
        raise bad_request("Le mot de passe actuel est incorrect.", code="wrong_password")
    ctx.login_throttle.clear_key(key)
    if problem := password_problem(body.next, user.email):
        raise unprocessable(problem[1], code=problem[0])
    conn.execute(
        update(app_user)
        .where(app_user.c.id == user.user_id)
        .values(password_hash=hash_password(body.next), token_version=app_user.c.token_version + 1)
    )
    return TokenOut(token=issue_token(ctx, conn, user.user_id))


@router.post("/logout-all", status_code=204)
def logout_all(user: CurrentUser, conn: Conn) -> Response:
    bump_token_version(conn, user.user_id)
    return Response(status_code=204)
