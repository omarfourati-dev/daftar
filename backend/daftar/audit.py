"""Change log (spec stock-hygiène 8, start of the audit log of security review N4): who changed, corrected or
deleted what, when, old → new, and why.

- :func:`record` writes one entry inside the request's transaction (the change and its entry commit together);
  ``before``/``after`` are small JSON snapshots (dates as ISO text, no secrets, no patient data beyond a name).
  :func:`diff` keeps only what changed, under the names the web shows (codes, not translations – the web words them).
  An ``update`` names its object in ``before`` (``product``, ``supplier``, ``task``, ``equipment``; a corrected receipt
  line or proof also its day and author); ``after`` holds only the new values.
- Entities: ``stock_receipt``, ``stock_receipt_line``, ``stock_movement``, ``stock_product``, ``supplier`` (stock) and
  ``hygiene_task``, ``equipment``, ``hygiene_task_done`` (hygiene).
- ``GET /api/audit-log?entity=a,b&limit=`` (owner) → ``[{id, at, userName, entity, entityId, action, before, after,
  reason}]``, newest first – each module asks for its own entities. The user's name is kept with the entry, so it
  stays readable when the account is gone.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from sqlalchemy import Connection, insert, select

from .clock import iso_tunis
from .deps import Conn, OwnerUser, Principal
from .schemas import ApiModel, TunisDateTime
from .tables import audit_log

router = APIRouter(prefix="/api/audit-log", tags=["audit"])

Action = Literal["create", "update", "delete"]


def jsonable(value: Any) -> Any:
    """Dates and instants as text, recursively – the snapshot must fit into JSONB."""
    if isinstance(value, datetime):
        return iso_tunis(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def diff(old: dict[str, Any], new: dict[str, Any], names: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(before, after)`` of the fields in ``names`` (field → key in the log) whose value in ``new`` differs from
    ``old``; fields missing in ``new`` did not change."""
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for field, key in names.items():
        if field in new and new[field] != old.get(field):
            before[key], after[key] = old.get(field), new[field]
    return before, after


def record(
    conn: Connection,
    user: Principal,
    *,
    entity: str,
    entity_id: int,
    action: Action,
    now: datetime,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
) -> None:
    conn.execute(
        insert(audit_log).values(
            practice_id=user.pid, user_id=user.user_id, user_name=user.name[:120], at=now, entity=entity,
            entity_id=entity_id, action=action, before=jsonable(before) if before is not None else None,
            after=jsonable(after) if after is not None else None, reason=reason[:300],
        )
    )


class AuditEntry(ApiModel):
    id: int
    at: TunisDateTime
    user_name: str
    entity: str
    entity_id: int
    action: Action
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str


@router.get("")
def list_entries(
    user: OwnerUser,
    conn: Conn,
    entity: Annotated[str | None, Query(pattern=r"^[a-z_]{1,40}(,[a-z_]{1,40}){0,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditEntry]:
    conditions = [audit_log.c.practice_id == user.pid]
    if entity is not None:
        conditions.append(audit_log.c.entity.in_(entity.split(",")))
    rows = conn.execute(
        select(audit_log).where(*conditions).order_by(audit_log.c.at.desc(), audit_log.c.id.desc()).limit(limit)
    ).all()
    return [AuditEntry.model_validate(r, from_attributes=True) for r in rows]
