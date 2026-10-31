"""The one place where API routers are registered.

Each feature module is its own file with its own ``router = APIRouter(...)`` (e.g. ``daftar/patients.py``).
To add one: import the module here and append its router to :data:`ROUTERS`. Order does not matter as long as
paths do not overlap; everything here is registered before the ``/api/*`` 404 and the static catch-all.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import auth, hosts, invitations
from . import billing  # be-patienten
from . import demo  # be-patienten
from . import export  # be-patienten
from . import feedback  # be-patienten
from . import finance  # be-patienten
from . import imports  # be-patienten
from . import overview  # be-patienten
from . import patients  # be-patienten
from . import pilot  # be-patienten
from . import reminders  # be-patienten
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
from . import booking
from . import queue_next
from . import audit, stock, stock_moves, stock_report

ROUTERS: list[APIRouter] = [
    auth.router,
    invitations.router,
    hosts.router,
    patients.router,
    finance.router,
    reminders.router,
    overview.router,
    pilot.public_router,
    pilot.admin_router,
    feedback.router,
    feedback.admin_router,
    export.router,
    demo.router,
    billing.router,
    billing.admin_router,
    billing.public_router,
    imports.router,
    imports.template_router,
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
    booking.router,
    queue_next.router,
    audit.router,
    stock.router,
    stock_moves.router,
    stock_report.router,
]
