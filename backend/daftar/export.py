"""``GET /api/practice/export`` (owner): every piece of data of the practice as one JSON download (E4, GDPR).

Allowed with a suspended subscription (reading is never blocked). Never exported: password and token hashes,
token versions, public bearer tokens (display screen, queue tickets, booking links), the admin's internal notes,
uploaded import files and password-reset links. Keys are camelCase like the API, instants ISO-8601 in Tunis time.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic.alias_generators import to_camel
from sqlalchemy import Connection, Table, select

from .clock import iso_tunis, today_tunis
from .deps import Conn, Ctx, OwnerUser
from .tables import (
    app_user,
    appointment,
    cash_closing,
    feedback,
    import_template,
    invitation,
    invoice,
    patient,
    payment,
    practice,
    practice_closure,
    practitioner,
    queue_entry,
    service,
    treatment,
)

router = APIRouter(prefix="/api/practice", tags=["practice"])

FORMAT = "daftar-export/1"
#: Columns that never leave the server.
SECRET_COLUMNS = frozenset(
    {"password_hash", "token_version", "token_hash", "booking_token_hash", "ticket_token", "display_token", "admin_notes"}
)
#: Export key → table (each filtered on practice_id, ordered by its primary key).
SECTIONS: tuple[tuple[str, Table], ...] = (
    ("users", app_user),
    ("invitations", invitation),
    ("practitioners", practitioner),
    ("services", service),
    ("closures", practice_closure),
    ("patients", patient),
    ("appointments", appointment),
    ("queueEntries", queue_entry),
    ("treatments", treatment),
    ("payments", payment),
    ("cashClosings", cash_closing),
    ("invoices", invoice),
    ("importTemplates", import_template),
    ("feedback", feedback),
)


def _value(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_tunis(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _rows(conn: Connection, table: Table, *conditions: Any) -> list[dict[str, Any]]:
    columns = [c for c in table.columns if c.name not in SECRET_COLUMNS]
    rows = conn.execute(select(*columns).where(*conditions).order_by(*table.primary_key.columns))
    return [{to_camel(k): _value(v) for k, v in row._mapping.items()} for row in rows]


def export_practice(conn: Connection, practice_id: int, now: datetime) -> dict[str, Any]:
    (practice_data,) = _rows(conn, practice, practice.c.id == practice_id)
    data: dict[str, Any] = {"format": FORMAT, "exportedAt": iso_tunis(now), "practice": practice_data}
    for key, table in SECTIONS:
        data[key] = _rows(conn, table, table.c.practice_id == practice_id)
    return data


@router.get("/export")
def export(user: OwnerUser, ctx: Ctx, conn: Conn) -> Response:
    data = export_practice(conn, user.pid, ctx.clock.now())
    filename = f"daftar-export-{data['practice']['slug']}-{today_tunis(ctx.clock).isoformat()}.json"
    return Response(
        json.dumps(data, ensure_ascii=False, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
