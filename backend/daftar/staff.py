"""``/api/staff``: the team of a practice (sections 5 and 15).

Reading: every staff role. Changing: the owner (402 while the subscription is suspended).
- ``GET /api/staff`` → ``[{id, name, email, role, createdAt}]``
- ``PATCH /api/staff/{id} {role: 'dentist'|'assistant'}`` · ``DELETE /api/staff/{id}`` – never oneself
  (409 ``self_not_allowed``), never an owner (409 ``owner_protected``)
- ``GET /api/staff/invitations`` → open staff invitations ``[{id, role, createdAt, expiresAt}]``;
  ``POST /api/staff/invitations {role}`` → 201 ``{id, token, expiresAt}`` (link ``/invitation#<token>``, 7 days);
  ``DELETE /api/staff/invitations/{id}`` (the admin's owner links are not listed and cannot be deleted here)
- ``POST /api/staff/{id}/reset-link`` → 201 ``{token, expiresAt}`` (link ``/reinitialiser#<token>``, 24 h)
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from sqlalchemy import Connection, delete, select, update

from .deps import Conn, Ctx, OwnerUser, OwnerWriter, Principal, StaffUser
from .invitations import create_invitation
from .password_reset import ResetLinkOut, create_reset_link
from .problems import conflict, not_found
from .schemas import ApiModel, Role, TunisDateTime
from .tables import app_user, invitation

router = APIRouter(prefix="/api/staff", tags=["staff"])

StaffRole = Literal["dentist", "assistant"]
STAFF_ROLES = ("dentist", "assistant")


class MemberOut(ApiModel):
    id: int
    name: str
    email: str
    role: Role
    created_at: TunisDateTime


class RoleIn(ApiModel):
    role: StaffRole


class InvitationIn(ApiModel):
    role: StaffRole


class InvitationOut(ApiModel):
    id: int
    role: StaffRole
    created_at: TunisDateTime
    expires_at: TunisDateTime


class CreatedInvitationOut(ApiModel):
    id: int
    token: str
    expires_at: TunisDateTime


def _member(conn: Connection, practice_id: int, user_id: int) -> MemberOut:
    row = conn.execute(
        select(app_user.c.id, app_user.c.name, app_user.c.email, app_user.c.role, app_user.c.created_at).where(
            app_user.c.id == user_id, app_user.c.practice_id == practice_id
        )
    ).first()
    if row is None:
        raise not_found()
    return MemberOut.model_validate(row, from_attributes=True)


def _changeable(conn: Connection, user: Principal, user_id: int) -> MemberOut:
    """A member the owner may change: of the practice (404), not oneself, not an owner (409)."""
    member = _member(conn, user.pid, user_id)
    if member.id == user.user_id:
        raise conflict("Vous ne pouvez pas faire cela pour votre propre compte.", code="self_not_allowed")
    if member.role == "owner":
        raise conflict("Le compte du titulaire ne peut pas être modifié ici.", code="owner_protected")
    return member


@router.get("")
def list_staff(user: StaffUser, conn: Conn) -> list[MemberOut]:
    rows = conn.execute(
        select(app_user.c.id, app_user.c.name, app_user.c.email, app_user.c.role, app_user.c.created_at)
        .where(app_user.c.practice_id == user.pid)
        .order_by(app_user.c.id)
    ).all()
    return [MemberOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/invitations")
def list_invitations(user: OwnerUser, ctx: Ctx, conn: Conn) -> list[InvitationOut]:
    rows = conn.execute(
        select(invitation.c.id, invitation.c.role, invitation.c.created_at, invitation.c.expires_at)
        .where(
            invitation.c.practice_id == user.pid,
            invitation.c.role.in_(STAFF_ROLES),
            invitation.c.used_at.is_(None),
            invitation.c.expires_at > ctx.clock.now(),
        )
        .order_by(invitation.c.created_at, invitation.c.id)
    ).all()
    return [InvitationOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/invitations", status_code=201)
def invite(body: InvitationIn, user: OwnerWriter, ctx: Ctx, conn: Conn) -> CreatedInvitationOut:
    created = create_invitation(conn, practice_id=user.pid, role=body.role, created_by=user.user_id, now=ctx.clock.now())
    return CreatedInvitationOut(id=created.id, token=created.token, expires_at=created.expires_at)


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke(invitation_id: int, user: OwnerWriter, conn: Conn) -> Response:
    result = conn.execute(
        delete(invitation).where(
            invitation.c.id == invitation_id, invitation.c.practice_id == user.pid, invitation.c.role.in_(STAFF_ROLES)
        )
    )
    if not result.rowcount:
        raise not_found()
    return Response(status_code=204)


@router.patch("/{user_id}")
def change_role(user_id: int, body: RoleIn, user: OwnerWriter, conn: Conn) -> MemberOut:
    _changeable(conn, user, user_id)
    conn.execute(update(app_user).where(app_user.c.id == user_id).values(role=body.role))
    return _member(conn, user.pid, user_id)


@router.delete("/{user_id}", status_code=204)
def remove(user_id: int, user: OwnerWriter, conn: Conn) -> Response:
    _changeable(conn, user, user_id)
    conn.execute(delete(app_user).where(app_user.c.id == user_id))
    return Response(status_code=204)


@router.post("/{user_id}/reset-link", status_code=201)
def reset_link(user_id: int, user: OwnerWriter, ctx: Ctx, conn: Conn) -> ResetLinkOut:
    _changeable(conn, user, user_id)
    created = create_reset_link(conn, user_id=user_id, created_by=user.user_id, now=ctx.clock.now())
    return ResetLinkOut(token=created.token, expires_at=created.expires_at)

