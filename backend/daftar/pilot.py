"""Pilot requests from the sales page (section 5) and their admin list.

- ``POST /api/public/pilot-requests {name, practice, city, phone, email?, message?, lang, website}`` → 202.
  ``website`` is a honeypot: when filled, the answer is the same 202 but nothing is stored. 5 per IP and hour.
- ``GET /api/admin/pilot-requests`` (newest first) · ``DELETE /api/admin/pilot-requests/{id}`` → 204.
- Requests are deleted after 12 months at the latest (privacy policy) – job ``pilot-request-cleanup``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import Field
from sqlalchemy import Connection, delete, insert, select

from .context import AppContext
from .deps import AdminUser, ClientIp, Conn, Ctx
from .phone import Phone
from .problems import not_found
from .schemas import ApiModel, Email, Lang, Name, TunisDateTime
from .tables import pilot_request

public_router = APIRouter(prefix="/api/public/pilot-requests", tags=["public"])
admin_router = APIRouter(prefix="/api/admin/pilot-requests", tags=["admin"])

PER_IP = 5
WINDOW = timedelta(hours=1)
#: Pilot requests are kept at most this long (privacy policy: "au plus tard après 12 mois").
RETENTION = timedelta(days=365)


class PilotRequestIn(ApiModel):
    name: Name
    practice: Name
    city: Name
    phone: Phone
    email: Email | None = None
    message: Annotated[str, Field(max_length=2000)] = ""
    lang: Lang = "fr"
    website: Annotated[str, Field(max_length=1000)] = ""


class PilotRequestOut(ApiModel):
    id: int
    name: str
    practice: str
    city: str
    phone: str
    email: str | None
    message: str
    lang: str
    created_at: TunisDateTime


@public_router.post("", status_code=202)
def create_pilot_request(body: PilotRequestIn, ctx: Ctx, conn: Conn, ip: ClientIp) -> Response:
    ctx.limiter("pilot-request-ip", PER_IP, WINDOW).enforce(ip)
    if body.website:
        return Response(status_code=202)  # a bot filled the hidden field – pretend success
    conn.execute(
        insert(pilot_request).values(
            name=body.name,
            practice=body.practice,
            city=body.city,
            phone=body.phone,
            email=body.email.lower() if body.email else None,
            message=body.message,
            lang=body.lang,
            created_at=ctx.clock.now(),
        )
    )
    ctx.metrics.pilot_requests.inc()
    return Response(status_code=202)


@admin_router.get("")
def list_pilot_requests(_: AdminUser, conn: Conn) -> list[PilotRequestOut]:
    rows = conn.execute(select(pilot_request).order_by(pilot_request.c.created_at.desc(), pilot_request.c.id.desc()))
    return [PilotRequestOut.model_validate(r, from_attributes=True) for r in rows]


@admin_router.delete("/{request_id}", status_code=204)
def delete_pilot_request(request_id: int, _: AdminUser, conn: Conn) -> Response:
    if not conn.execute(delete(pilot_request).where(pilot_request.c.id == request_id)).rowcount:
        raise not_found()
    return Response(status_code=204)


def delete_old_pilot_requests(conn: Connection, now: datetime) -> int:
    return conn.execute(delete(pilot_request).where(pilot_request.c.created_at < now - RETENTION)).rowcount or 0


def cleanup_pilot_requests(ctx: AppContext) -> None:
    with ctx.engine.begin() as conn:
        delete_old_pilot_requests(conn, ctx.clock.now())
