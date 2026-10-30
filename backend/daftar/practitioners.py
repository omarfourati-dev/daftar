"""``/api/practitioners``: the people who treat patients (section 11.2) – not accounts; ``userId`` may link one.

- ``GET`` (every staff role) → ``[Practitioner]`` ordered by ``sort``, then id, inactive ones included (``active``);
- ``POST`` / ``PATCH /{id}`` / ``DELETE /{id}`` (owner). A practitioner who has appointments cannot be deleted
  (409 ``practitioner_in_use`` – deactivate them instead: ``active: false``), so no appointment loses its practitioner.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Response
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import Connection, delete, exists, func, insert, select, update

from .catalog import Specialty
from .deps import Conn, OwnerWriter, StaffUser
from .practice_settings import BrandColor
from .problems import conflict, not_found, unprocessable
from .schemas import ApiModel, Name
from .tables import app_user, appointment, practitioner

router = APIRouter(prefix="/api/practitioners", tags=["practitioners"])

Title = Annotated[str, Field(max_length=20)]
Sort = Annotated[int, Field(ge=0, le=10_000)]


class PractitionerOut(ApiModel):
    id: int
    name: str
    title: str
    specialty: str | None
    color: str
    user_id: int | None
    online_bookable: bool
    active: bool
    sort: int


class PractitionerIn(ApiModel):
    name: Name
    title: Title = "Dr."
    specialty: Specialty | None = None
    color: BrandColor = "#0f766e"
    user_id: int | None = None
    online_bookable: StrictBool = True
    active: StrictBool = True
    sort: Sort | None = None


class PractitionerPatch(ApiModel):
    name: Name | None = None
    title: Title | None = None
    specialty: Specialty | None = None
    color: BrandColor | None = None
    user_id: int | None = None
    online_bookable: StrictBool | None = None
    active: StrictBool | None = None
    sort: Sort | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> PractitionerPatch:
        for name in self.model_fields_set - {"specialty", "user_id"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


def _check_user(conn: Connection, practice_id: int, user_id: int | None) -> None:
    if user_id is None:
        return
    found = conn.execute(
        select(app_user.c.id).where(app_user.c.id == user_id, app_user.c.practice_id == practice_id)
    ).first()
    if found is None:
        raise unprocessable("Ce compte n'appartient pas au cabinet.", code="invalid_user")


def next_sort(conn: Connection, table: Any, practice_id: int) -> int:
    """One more than the highest ``sort`` of the practice's rows in ``table``."""
    return conn.execute(select(func.coalesce(func.max(table.c.sort), 0) + 1).where(table.c.practice_id == practice_id)).scalar_one()


def _get(conn: Connection, practice_id: int, practitioner_id: int) -> PractitionerOut:
    row = conn.execute(
        select(practitioner).where(practitioner.c.id == practitioner_id, practitioner.c.practice_id == practice_id)
    ).first()
    if row is None:
        raise not_found()
    return PractitionerOut.model_validate(row, from_attributes=True)


@router.get("")
def list_practitioners(user: StaffUser, conn: Conn) -> list[PractitionerOut]:
    rows = conn.execute(
        select(practitioner).where(practitioner.c.practice_id == user.pid).order_by(practitioner.c.sort, practitioner.c.id)
    ).all()
    return [PractitionerOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", status_code=201)
def create_practitioner(body: PractitionerIn, user: OwnerWriter, conn: Conn) -> PractitionerOut:
    _check_user(conn, user.pid, body.user_id)
    values = body.model_dump(by_alias=False)
    if values["sort"] is None:
        values["sort"] = next_sort(conn, practitioner, user.pid)
    new_id = conn.execute(insert(practitioner).values(practice_id=user.pid, **values).returning(practitioner.c.id)).scalar_one()
    return _get(conn, user.pid, new_id)


@router.patch("/{practitioner_id}")
def patch_practitioner(practitioner_id: int, body: PractitionerPatch, user: OwnerWriter, conn: Conn) -> PractitionerOut:
    _get(conn, user.pid, practitioner_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    if "user_id" in values:
        _check_user(conn, user.pid, values["user_id"])
    if values:
        conn.execute(update(practitioner).where(practitioner.c.id == practitioner_id).values(**values))
    return _get(conn, user.pid, practitioner_id)


@router.delete("/{practitioner_id}", status_code=204)
def delete_practitioner(practitioner_id: int, user: OwnerWriter, conn: Conn) -> Response:
    _get(conn, user.pid, practitioner_id)
    used = conn.execute(select(exists().where(appointment.c.practitioner_id == practitioner_id))).scalar_one()
    if used:
        raise conflict(
            "Ce praticien a des rendez-vous : désactivez-le plutôt que de le supprimer.", code="practitioner_in_use"
        )
    conn.execute(delete(practitioner).where(practitioner.c.id == practitioner_id))
    return Response(status_code=204)
