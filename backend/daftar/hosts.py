"""Hosts: the main domain, the app's own host ``app.<BASE_DOMAIN>`` and the practice sub-domains ``<slug>.<BASE_DOMAIN>``.

- main domain ``<BASE_DOMAIN>`` (and every other host): landing, legal texts, static files – it shows Google AdSense,
  so the app never runs there and nobody signs in there; app paths move to the app host (301, daftar/static.py);
- ``app.<BASE_DOMAIN>`` (the slug ``app`` is reserved): the whole SPA – admin, every practice's staff, demo,
  invitations, password reset, booking pages ``/r/<slug>`` (fixlist 1: the token in localStorage lives on an origin
  without third-party scripts);
- ``<slug>.<BASE_DOMAIN>``: the practice's booking page and its own installable app.

- :func:`subdomain_label` – the label in front of the base domain (or None for the main domain, localhost, …);
- :func:`is_app_host`, :func:`site_origin` – the app host and the origin of a host name (``https://…``; locally
  ``http://…:<port>``);
- :func:`practice_for_host` – the practice of a request's host (None on the main domain or for unknown slugs);
- ``GET /api/public/tls-check?domain=`` – Caddy's on-demand TLS ``ask``: 200 for the app host and for an existing,
  non-demo practice that is not suspended or canceled, 404 otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Request, Response
from sqlalchemy import Connection, Engine, select

from .deps import Ctx
from .problems import not_found
from .slugs import slug_problem
from .tables import practice

router = APIRouter(prefix="/api/public", tags=["public"])

#: A practice in these statuses gets no certificate (its sub-domain stops working).
CLOSED_STATUSES = ("suspended", "canceled")
#: ``app.<BASE_DOMAIN>`` – the app's own origin (``app`` is a reserved slug, see daftar/slugs.py).
APP_LABEL = "app"


def normalize_host(host: str | None) -> str:
    """Lower-case host without port and trailing dot."""
    if not host:
        return ""
    host = host.strip().lower()
    if host.startswith("["):  # IPv6 literal
        return host
    return host.split(":", 1)[0].rstrip(".")


def subdomain_label(host: str | None, base_domain: str) -> str | None:
    """``cabinet-lac.daftar.omarfourati.de`` → ``cabinet-lac``; None for the base domain and foreign hosts."""
    name = normalize_host(host)
    suffix = "." + base_domain
    if not name.endswith(suffix) or len(name) == len(suffix):
        return None
    return name[: -len(suffix)]


def is_app_host(host: str | None, base_domain: str) -> bool:
    return subdomain_label(host, base_domain) == APP_LABEL


def site_origin(name: str, request_host: str | None) -> str:
    """``https://<name>``; locally (``localhost``, ``*.localhost``) ``http://<name>`` with the port of the request."""
    if name != "localhost" and not name.endswith(".localhost"):
        return f"https://{name}"
    port = (request_host or "").rpartition(":")[2]
    return f"http://{name}" + (f":{port}" if port.isdigit() else "")


@dataclass(frozen=True)
class HostPractice:
    id: int
    name: str
    slug: str
    brand_color: str
    is_demo: bool
    status: str


def practice_by_slug(conn: Connection, slug: str) -> HostPractice | None:
    if slug_problem(slug) is not None:
        return None
    row = conn.execute(
        select(practice.c.id, practice.c.name, practice.c.slug, practice.c.brand_color, practice.c.is_demo, practice.c.status)
        .where(practice.c.slug == slug)
    ).first()
    return HostPractice(*row) if row else None


def practice_for_host(engine: Engine, host: str | None, base_domain: str) -> tuple[bool, HostPractice | None]:
    """``(is_practice_host, practice)`` – a practice host with an unknown slug gives ``(True, None)``."""
    label = subdomain_label(host, base_domain)
    if label is None:
        return False, None
    with engine.connect() as conn:
        return True, practice_by_slug(conn, label)


@router.get("/tls-check", include_in_schema=False)
def tls_check(request: Request, ctx: Ctx, domain: str = "") -> Response:
    if is_app_host(domain, ctx.settings.base_domain):
        return Response(status_code=200)
    is_practice_host, found = practice_for_host(ctx.engine, domain, ctx.settings.base_domain)
    if not is_practice_host or found is None or found.is_demo or found.status in CLOSED_STATUSES:
        raise not_found()
    return Response(status_code=200)
