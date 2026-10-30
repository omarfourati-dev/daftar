"""Base model and field types for the JSON API.

- Fields are snake_case in Python and camelCase in JSON (``first_name`` ↔ ``firstName``), both ways.
- Instants serialize as ISO-8601 with the Tunis offset (``TunisDateTime``), days as ``YYYY-MM-DD`` (plain ``date``).
- Unknown input fields are ignored; strings are stripped.

Example::

    class PatientOut(ApiModel):
        id: int
        first_name: str
        created_at: TunisDateTime

    class PatientIn(ApiModel):
        first_name: Name
        phone: Phone
        notes: Text = ""
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel

from .clock import iso_tunis

Role = Literal["admin", "owner", "dentist", "assistant"]
PracticeRole = Literal["owner", "dentist", "assistant"]
Lang = Literal["fr", "ar"]

ROLES: tuple[Role, ...] = ("admin", "owner", "dentist", "assistant")
PRACTICE_ROLES: tuple[PracticeRole, ...] = ("owner", "dentist", "assistant")


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        str_strip_whitespace=True,
        extra="ignore",
    )


#: Output: an aware datetime rendered as ``2026-10-30T09:30:00+01:00``.
TunisDateTime = Annotated[datetime, PlainSerializer(iso_tunis, return_type=str)]
#: Input: an ISO-8601 instant that must carry an offset (``…+01:00`` or ``…Z``).
InstantIn = AwareDatetime
#: A person's or practice's name: 1–120 characters after stripping.
Name = Annotated[str, Field(min_length=1, max_length=120)]
#: Free text such as notes: up to 2000 characters, may be empty.
Text = Annotated[str, Field(max_length=2000)]
#: An e-mail address (light check, lower-cased by the code that stores it).
Email = Annotated[str, Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
