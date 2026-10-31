"""Fixtures of the practice / appointments / queue / online booking tests (``tests/termine``).

The clock stands on Friday 30.10.2026, 09:00 in Tunis (``T0``). Default opening hours: Monday–Saturday
08:00–12:30 and 14:00–18:00, Sunday closed. Useful days: ``FRI`` 30.10 (today), ``SAT`` 31.10, ``SUN`` 1.11 (closed),
``MON`` 2.11.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any

import pytest

from daftar.clock import TUNIS
from tests.conftest import TestUser

Factory = Callable[..., Any]

FRI = date(2026, 10, 30)
SAT = date(2026, 10, 31)
SUN = date(2026, 11, 1)
MON = date(2026, 11, 2)
TUE = date(2026, 11, 3)


def at(day: date, hhmm: str) -> datetime:
    """An aware Tunis instant: ``at(MON, "09:30")``."""
    return datetime.combine(day, time.fromisoformat(hhmm), tzinfo=TUNIS)


def iso(day: date, hhmm: str) -> str:
    """The API form of a Tunis instant: ``iso(MON, "09:30")`` → ``"2026-11-02T09:30:00+01:00"``."""
    return at(day, hhmm).isoformat(timespec="seconds")


@pytest.fixture
def as_user(auth_headers: Callable[[TestUser], dict[str, str]], make_user: Factory) -> Callable[..., dict[str, str]]:
    """``as_user(practice, "assistant")`` → auth headers of a new user with that role in that practice."""

    def make(practice_row: Any = None, role: str = "owner") -> dict[str, str]:
        return auth_headers(make_user(practice_row, role))

    return make
