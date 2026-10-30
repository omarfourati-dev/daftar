"""Errors as RFC 9457 ``application/problem+json``: ``{type, title, status, detail, code}``.

Raise :class:`ApiError` (or one of the helpers) anywhere in a handler or dependency; the handlers installed by
:func:`install_problem_handlers` turn it into the response. ``code`` is a stable machine-readable key that the web app
translates (``errors.<code>`` in web/src/lib/i18n); ``detail`` is a French fallback text for humans and logs.
Never put personal data or secrets into ``detail``.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
log = logging.getLogger("daftar")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        detail: str | None = None,
        *,
        code: str | None = None,
        title: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or "")
        self.status = status
        self.detail = detail
        self.code = code
        self.title = title or HTTPStatus(status).phrase
        self.headers = headers


def problem_response(
    status: int,
    detail: str | None = None,
    *,
    code: str | None = None,
    title: str | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


# --- helpers: raise these ---------------------------------------------------------------------------------------

def bad_request(detail: str = "Requête invalide.", code: str = "bad_request") -> ApiError:
    return ApiError(400, detail, code=code)


def unauthorized(detail: str = "Veuillez vous connecter.", code: str = "unauthorized") -> ApiError:
    return ApiError(401, detail, code=code)


def forbidden(detail: str = "Action non autorisée.", code: str = "forbidden") -> ApiError:
    return ApiError(403, detail, code=code)


def not_found(detail: str = "Introuvable.", code: str = "not_found") -> ApiError:
    """Also for IDs of another practice: never 403, so nothing leaks about foreign data."""
    return ApiError(404, detail, code=code)


def conflict(detail: str, code: str = "conflict") -> ApiError:
    return ApiError(409, detail, code=code)


def unprocessable(detail: str, code: str = "validation") -> ApiError:
    return ApiError(422, detail, code=code)


def too_many_requests(
    detail: str = "Trop de tentatives. Veuillez réessayer plus tard.", retry_after: int | None = None
) -> ApiError:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return ApiError(429, detail, code="too_many_requests", headers=headers)


# --- handlers ---------------------------------------------------------------------------------------------------

def _field(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts)


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return problem_response(exc.status, exc.detail, code=exc.code, title=exc.title, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != HTTPStatus(exc.status_code).phrase else None
        return problem_response(exc.status_code, detail, code=codes.get(exc.status_code), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo the submitted values (passwords!): only field, error type and message.
        errors = [
            {"field": _field(tuple(e.get("loc", ()))), "type": e.get("type"), "message": e.get("msg")}
            for e in exc.errors()
        ]
        first = exc.errors()[0] if exc.errors() else {}
        detail = "Les données envoyées sont invalides."
        code = "validation"
        # Our own validators raise ValueError("code: Texte") – e.g. the phone number – and win over the generic text.
        if first.get("type") == "value_error":
            message = str(first.get("msg", "")).removeprefix("Value error, ")
            if ": " in message:
                code, detail = message.split(": ", 1)
            else:
                detail = message
        return problem_response(422, detail, code=code, extra={"errors": errors})

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("error %s %s %s", request.method, request.url.path, type(exc).__name__, exc_info=exc)
        return problem_response(500, "Une erreur est survenue.", code="server_error")
