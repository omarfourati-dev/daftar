"""The one place where API routers are registered.

Each feature module is its own file with its own ``router = APIRouter(...)`` (e.g. ``daftar/patients.py``).
To add one: import the module here and append its router to :data:`ROUTERS`. Order does not matter as long as
paths do not overlap; everything here is registered before the ``/api/*`` 404 and the static catch-all.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import auth, hosts, invitations
from . import practice_settings
from . import practitioners
from . import services
from . import closures
from . import staff
from . import password_reset
from . import admin_practices
from . import onboarding
from . import queue
from . import availability
from . import appointments
from . import series

ROUTERS: list[APIRouter] = [
    auth.router,
    invitations.router,
    hosts.router,
    practice_settings.router,
    practitioners.router,
    services.router,
    closures.router,
    staff.router,
    password_reset.router,
    admin_practices.router,
    onboarding.router,
    queue.router,
    queue.public_router,
    availability.router,
    appointments.router,
    series.router,
]
