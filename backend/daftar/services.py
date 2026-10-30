"""``/api/services``: the practice's catalog of acts / consultations (section 11.2).

- ``GET`` (every staff role) → ``[Service]`` ordered by ``sort``, then id (inactive ones included, see ``active``);
- ``POST`` / ``PATCH /{id}`` / ``DELETE /{id}`` (owner). Deleting keeps the appointments (their ``serviceId`` becomes
  null); to hide a service from new appointments and the booking page set ``active: false``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import Field, StrictBool, model_validator
from sqlalchemy import Connection, delete, insert, select, update

from .deps import Conn, OwnerWriter, StaffUser
from .money import Millimes
from .practice_settings import BrandColor, DurationMin
from .practitioners import Sort, next_sort
from .problems import not_found
from .schemas import ApiModel, Name
from .tables import service

router = APIRouter(prefix="/api/services", tags=["services"])

NameAr = Annotated[str, Field(max_length=120)]


class ServiceOut(ApiModel):
    id: int
    name_fr: str
    name_ar: str
    duration_min: int
    price_millimes: int | None
    online_bookable: bool
    color: str | None
    active: bool
    sort: int


class ServiceIn(ApiModel):
    name_fr: Name
    name_ar: NameAr = ""
    duration_min: DurationMin
    price_millimes: Millimes | None = None
    online_bookable: StrictBool = False
    color: BrandColor | None = None
    active: StrictBool = True
    sort: Sort | None = None


class ServicePatch(ApiModel):
    name_fr: Name | None = None
    name_ar: NameAr | None = None
    duration_min: DurationMin | None = None
    price_millimes: Millimes | None = None
    online_bookable: StrictBool | None = None
    color: BrandColor | None = None
    active: StrictBool | None = None
    sort: Sort | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> ServicePatch:
        for name in self.model_fields_set - {"price_millimes", "color"}:
            if getattr(self, name) is None:
                raise ValueError("validation: Ce champ ne peut pas être vide.")
        return self


def _get(conn: Connection, practice_id: int, service_id: int) -> ServiceOut:
    row = conn.execute(select(service).where(service.c.id == service_id, service.c.practice_id == practice_id)).first()
    if row is None:
        raise not_found()
    return ServiceOut.model_validate(row, from_attributes=True)


@router.get("")
def list_services(user: StaffUser, conn: Conn) -> list[ServiceOut]:
    rows = conn.execute(select(service).where(service.c.practice_id == user.pid).order_by(service.c.sort, service.c.id)).all()
    return [ServiceOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", status_code=201)
def create_service(body: ServiceIn, user: OwnerWriter, conn: Conn) -> ServiceOut:
    values = body.model_dump(by_alias=False)
    if values["sort"] is None:
        values["sort"] = next_sort(conn, service, user.pid)
    new_id = conn.execute(insert(service).values(practice_id=user.pid, **values).returning(service.c.id)).scalar_one()
    return _get(conn, user.pid, new_id)


@router.patch("/{service_id}")
def patch_service(service_id: int, body: ServicePatch, user: OwnerWriter, conn: Conn) -> ServiceOut:
    _get(conn, user.pid, service_id)
    values = body.model_dump(exclude_unset=True, by_alias=False)
    if values:
        conn.execute(update(service).where(service.c.id == service_id).values(**values))
    return _get(conn, user.pid, service_id)


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, user: OwnerWriter, conn: Conn) -> Response:
    _get(conn, user.pid, service_id)
    conn.execute(delete(service).where(service.c.id == service_id))
    return Response(status_code=204)
