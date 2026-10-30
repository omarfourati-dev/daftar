"""One pure-ASGI middleware for every response: security headers, request log, HTTP metrics, last-resort 500.

The CSP is built once at startup; ``script-src`` contains the hashes of the inline scripts of the SPA shell
(``200.html``), so SvelteKit's bootstrap script runs and nothing else inline does. No external hosts anywhere.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .metrics import Metrics
from .problems import problem_response

log = logging.getLogger("daftar.http")
error_log = logging.getLogger("daftar")
QUIET_PATHS = frozenset({"/healthz", "/metrics"})


def build_csp(script_hashes: list[str]) -> str:
    script_src = " ".join(["'self'", *(f"'sha256-{h}'" for h in script_hashes)])
    return (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "manifest-src 'self'; "
        "worker-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


def security_headers(csp: str) -> dict[str, str]:
    return {
        "Content-Security-Policy": csp,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }


def route_label(scope: Scope) -> str:
    """The route template (``/api/patients/{patient_id}``), ``static`` for files/SPA, ``unmatched`` otherwise."""
    route: Any = scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        return "unmatched"
    if path == "/{path:path}":
        return "static"
    return str(path)


class HttpMiddleware:
    def __init__(self, app: ASGIApp, *, metrics: Metrics, csp: str, log_requests: bool = True) -> None:
        self.app = app
        self.metrics = metrics
        self.headers = security_headers(csp)
        self.log_requests = log_requests

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        state = {"status": 500, "started": False}

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["started"] = True
                headers = MutableHeaders(scope=message)
                for name, value in self.headers.items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as exc:
            error_log.error("error %s %s %s", scope.get("method"), scope.get("path"), type(exc).__name__, exc_info=exc)
            if state["started"]:
                raise
            response = problem_response(500, "Une erreur est survenue.", code="server_error")
            await response(scope, receive, send_with_headers)
        finally:
            elapsed = time.perf_counter() - start
            method = scope.get("method", "")
            route = route_label(scope)
            status = int(state["status"])
            self.metrics.http_requests.labels(method, route, str(status)).inc()
            self.metrics.http_duration.labels(method, route).observe(elapsed)
            path = scope.get("path", "")
            if self.log_requests and path not in QUIET_PATHS:
                # never the query string – it may carry tokens
                log.info("%s %s %s %dms", method, path, status, round(elapsed * 1000))
