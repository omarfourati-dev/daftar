"""The one place where API routers are registered.

Each feature module is its own file with its own ``router = APIRouter(...)`` (e.g. ``daftar/patients.py``).
To add one: import the module here and append its router to :data:`ROUTERS`. Order does not matter as long as
paths do not overlap; everything here is registered before the ``/api/*`` 404 and the static catch-all.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import auth, hosts, invitations
from . import finance  # be-patienten
from . import patients  # be-patienten
from . import reminders  # be-patienten

ROUTERS: list[APIRouter] = [
    auth.router,
    invitations.router,
    hosts.router,
    patients.router,
    finance.router,
    reminders.router,
]
