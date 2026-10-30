"""The application factory: ``create_app(settings, clock)`` builds a fully wired FastAPI app.

Nothing global: engine, metrics, limiters and the clock live in the app's :class:`AppContext`, so every test gets a
fresh app. Production entry point: ``python -m daftar`` (see ``__main__.py``) after ``alembic upgrade head``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import Engine
from starlette.routing import Match

from .bootstrap import bootstrap_admin
from .branding import ICONS, initials, manifest, render_icon
from .hosts import APP_LABEL, HostPractice, is_app_host, practice_for_host, site_origin
from .clock import Clock, SystemClock
from .context import AppContext
from .db import make_engine, ping
from .http import HttpMiddleware, build_csp
from .jobs import JOBS, run_forever
from .metrics import Metrics, database_gauges
from .problems import install_problem_handlers, problem_response
from .routers import ROUTERS
from .settings import Settings
from .static import StaticSite
from .throttle import LoginThrottle
from .tokens import Tokens

log = logging.getLogger("daftar")
ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def create_app(
    settings: Settings,
    clock: Clock | None = None,
    *,
    engine: Engine | None = None,
    run_jobs: bool = True,
) -> FastAPI:
    clock = clock or SystemClock()
    engine = engine or make_engine(settings.database_url)
    metrics = Metrics()
    metrics.add_collector(database_gauges(engine))
    ctx = AppContext(
        settings=settings,
        clock=clock,
        engine=engine,
        metrics=metrics,
        tokens=Tokens(settings.jwt_secret, clock),
        login_throttle=LoginThrottle(clock),
    )
    site = StaticSite(settings.landing_dir, settings.web_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        bootstrap_admin(ctx)
        tasks = [asyncio.create_task(run_forever(job, ctx)) for job in JOBS] if run_jobs else []
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()

    app = FastAPI(
        title="Daftar",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        telemetry={"tracing": False, "metrics": False, "logs": False, "operation_spans": False, "auto_configure": False},
    )
    app.state.ctx = ctx
    app.state.site = site
    install_problem_handlers(app)

    for router in ROUTERS:
        app.include_router(router)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> Response:
        try:
            ping(engine)
        except Exception:
            log.warning("health check: database unreachable")
            return problem_response(503, "Base de données injoignable.", code="database_unavailable")
        return JSONResponse({"status": "ok"})

    @app.get("/metrics", include_in_schema=False)
    def prometheus() -> Response:
        return Response(metrics.render(), media_type=metrics.content_type)

    async def api_not_found(request: Request) -> Response:
        # a known path with another method is 405, not 404 (the catch-all would otherwise hide it)
        for route in app.router.routes:
            if getattr(route, "endpoint", None) in (api_not_found, static):
                continue
            match, _ = route.matches(dict(request.scope))
            if match is Match.PARTIAL:
                return problem_response(405, code="method_not_allowed")
        return problem_response(404, code="not_found")

    app.add_api_route("/api", api_not_found, methods=ALL_METHODS, include_in_schema=False)
    app.add_api_route("/api/{rest:path}", api_not_found, methods=ALL_METHODS, include_in_schema=False)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def static(request: Request) -> Response:
        host, base = request.headers.get("host"), settings.base_domain
        if is_app_host(host, base):
            return site.respond_app(request, site_origin(base, host))
        is_practice_host, host_practice = practice_for_host(engine, host, base)
        if not is_practice_host:
            return site.respond(request, site_origin(f"{APP_LABEL}.{base}", host))
        if host_practice is None:
            return site.not_found(request)
        return practice_page(request, host_practice)

    def practice_page(request: Request, p: HostPractice) -> Response:
        path = request.scope["path"]
        if path in ("/manifest.webmanifest", "/booking.webmanifest"):
            kind = "booking" if path.startswith("/booking") else "app"
            body = json.dumps(manifest(name=p.name, brand_color=p.brand_color, kind=kind), ensure_ascii=False)
            return Response(body, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})
        if path in ICONS:
            size, maskable = ICONS[path]
            png = render_icon(initials(p.name), p.brand_color, size, maskable)
            return Response(png, media_type="image/png", headers={"Cache-Control": "no-cache"})
        if path.startswith("/icons/practice-"):
            return site.not_found(request)
        return site.respond_practice(request, site_origin(settings.base_domain, request.headers.get("host")))

    app.add_middleware(
        HttpMiddleware, metrics=metrics, csp=build_csp(site.csp_hashes()), log_requests=settings.log_requests
    )
    return app
