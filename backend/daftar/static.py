"""Static delivery of the landing site and the SPA (design section 2), per host (see daftar/hosts.py).

Main domain ``<BASE_DOMAIN>`` (and every other host, :meth:`StaticSite.respond`) – landing, legal texts, files:
1. app routes (paths without a file extension under ``/app``, ``/connexion``, ``/invitation``, ``/reinitialiser``,
   ``/salle/``, ``/ticket/``, ``/r/``, and the page ``/rdv``) → 301 to the same path and query on
   ``app.<BASE_DOMAIN>`` (the browser keeps the fragment, e.g. ``/rdv#<token>``);
2. exact file in ``landing/``;
3. directory in ``landing/`` with ``index.html`` (without trailing slash: 308 redirect to ``…/``);
4. file from ``web/build`` (SvelteKit output), but never the SPA shell ``200.html`` – the app does not run here;
5. otherwise 404 (``landing/404.html`` when present, else problem+json). ``/api/*`` never gets here.

App host ``app.<BASE_DOMAIN>`` (:meth:`StaticSite.respond_app`): ``/`` → 302 ``/app``; app routes → ``200.html``;
files from ``web/build``; unknown ``/_app/…`` and ``/icons/…`` → 404; everything else (landing, legal texts) 302 to
the same path on the main domain.

On a practice sub-domain (``<slug>.<BASE_DOMAIN>``, see :meth:`StaticSite.respond_practice`): ``/``, ``/rdv``,
``/app…``, ``/connexion``, ``/invitation``, ``/reinitialiser`` → SPA; app assets (``/_app``, ``/icons``,
``/sw.js``, ``/favicon.svg``, ``/200.html``) as usual; everything else 302 to the same path on the main domain.
Manifests and icons of the practice come from daftar/branding.py (wired in app.py).

Traversal attempts (``..``, backslashes, control characters, ``//``, ``:``) get a hard 404, never the SPA.
Google AdSense: only the two home pages of the landing (``index.html`` and ``ar/index.html``, served for ``/`` and
``/ar/``) carry their own, relaxed CSP (:data:`daftar.http.ADS_CSP`); every other response keeps the strict one.
Caching: ``/_app/immutable/*`` one year immutable; fonts and images one day; everything else ``no-cache`` with
an ETag (so HTML, ``200.html``, ``sw.js`` and ``manifest.webmanifest`` are always revalidated).
"""

from __future__ import annotations

import base64
import hashlib
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from .http import ADS_CSP
from .problems import problem_response

SPA_SHELL = "200.html"
#: The landing pages that show Google AdSense (design section 7): the French and the Arabic home page.
AD_PAGES = ("index.html", "ar/index.html")
SPA_PREFIXES = ("/app", "/connexion", "/invitation", "/reinitialiser")
SPA_PREFIXES_WITH_TOKEN = ("/salle/", "/ticket/", "/r/")
#: Single SPA pages: the patient's link ``/rdv#<token>`` (fixlist 2; the token stays in the fragment, the old pages
#: ``/rdv/<token>`` are gone).
SPA_PAGES = ("/rdv",)
PRACTICE_SPA_PREFIXES = ("/app", "/connexion", "/invitation", "/reinitialiser")
PRACTICE_ASSET_PREFIXES = ("/_app/", "/icons/")
PRACTICE_ASSETS = ("/sw.js", "/favicon.svg", "/200.html")

IMMUTABLE = "public, max-age=31536000, immutable"
ONE_DAY = "public, max-age=86400"
NO_CACHE = "no-cache"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".ico": "image/x-icon",
    ".gif": "image/gif",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".pdf": "application/pdf",
    ".map": "application/json",
}
LONG_LIVED = {".woff2", ".woff", ".ttf", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".gif", ".svg"}

_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc\s*=)[^>]*>([\s\S]*?)</script>", re.IGNORECASE)


def inline_script_hashes(html: str) -> list[str]:
    """Base64 SHA-256 of every non-empty inline ``<script>`` – for ``script-src 'sha256-…'``."""
    return [
        base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
        for body in _INLINE_SCRIPT.findall(html)
        if body.strip()
    ]


def is_unsafe(path: str) -> bool:
    return (
        ".." in path
        or "\\" in path
        or ":" in path
        or path.startswith("//")
        or any(ord(c) < 0x20 or ord(c) == 0x7F for c in path)
    )


def decode_path(raw: str) -> str | None:
    """Percent-decodes once; None for malformed escapes or invalid UTF-8."""
    if re.search(r"%(?![0-9A-Fa-f]{2})", raw):
        return None
    try:
        return unquote(raw, errors="strict")
    except UnicodeDecodeError:
        return None


def is_spa_route(path: str) -> bool:
    last = path.rstrip("/").rsplit("/", 1)[-1]
    if "." in last:
        return False
    if path in SPA_PAGES or any(path == p or path.startswith(p + "/") for p in SPA_PREFIXES):
        return True
    return any(path.startswith(p) and len(path) > len(p) for p in SPA_PREFIXES_WITH_TOKEN)


@dataclass(frozen=True)
class StaticFile:
    body: bytes
    content_type: str
    cache_control: str
    etag: str
    csp: str | None = None  # own Content-Security-Policy (the AdSense home pages), else the middleware's strict one


class StaticSite:
    def __init__(self, landing_dir: Path | None, web_dir: Path | None) -> None:
        self.landing = landing_dir.resolve() if landing_dir and landing_dir.is_dir() else None
        self.web = web_dir.resolve() if web_dir and web_dir.is_dir() else None
        self._ad_pages = {(self.landing / rel).resolve() for rel in AD_PAGES} if self.landing else set()
        self._cache: dict[Path, StaticFile] = {}
        self._lock = threading.Lock()

    # --- lookups ------------------------------------------------------------------------------------------------

    def _file(self, root: Path | None, rel: str, *, immutable_ok: bool) -> StaticFile | None:
        if root is None or not rel:
            return None
        candidate = (root / rel).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        with self._lock:
            hit = self._cache.get(candidate)
        if hit is not None:
            return hit
        body = candidate.read_bytes()
        suffix = candidate.suffix.lower()
        if immutable_ok and rel.startswith("_app/immutable/"):
            cache = IMMUTABLE
        elif suffix in LONG_LIVED:
            cache = ONE_DAY
        else:
            cache = NO_CACHE
        etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
        csp = ADS_CSP if root == self.landing and candidate in self._ad_pages else None
        made = StaticFile(body, CONTENT_TYPES.get(suffix, "application/octet-stream"), cache, etag, csp)
        with self._lock:
            self._cache[candidate] = made
        return made

    def shell(self) -> StaticFile | None:
        return self._file(self.web, SPA_SHELL, immutable_ok=False)

    def csp_hashes(self) -> list[str]:
        shell = self.shell()
        return inline_script_hashes(shell.body.decode("utf-8")) if shell else []

    # --- request handling ---------------------------------------------------------------------------------------

    def respond(self, request: Request, app_origin: str) -> Response:
        """The main domain: landing, legal texts and files; app routes move to ``app_origin`` (301)."""
        path = self._path(request)
        if path is None:
            return self.not_found(request)
        if path == "/api" or path.startswith("/api/"):
            return problem_response(404, code="not_found")
        if is_spa_route(path):
            return RedirectResponse(app_origin + self._target(request), status_code=301)
        if path == "/" + SPA_SHELL:
            return self.not_found(request)
        return self._files(request, path)

    def respond_app(self, request: Request, main_origin: str) -> Response:
        """The app host ``app.<BASE_DOMAIN>``: the SPA and its files; the landing stays on ``main_origin``."""
        path = self._path(request)
        if path is None:
            return self.not_found(request)
        if path == "/":
            query = request.url.query
            return RedirectResponse("/app" + (f"?{query}" if query else ""), status_code=302)
        if is_spa_route(path):
            shell = self.shell()
            return self._send(request, shell) if shell else self.not_found(request)
        found = self._file(self.web, path.lstrip("/"), immutable_ok=True) if not path.endswith("/") else None
        if found is not None:
            return self._send(request, found)
        if path.startswith(PRACTICE_ASSET_PREFIXES):
            return self.not_found(request)
        return RedirectResponse(main_origin + self._target(request), status_code=302)

    def respond_practice(self, request: Request, main_origin: str) -> Response:
        """A request on an existing practice's sub-domain (manifests and icons are handled before)."""
        path = request.scope["path"]
        if is_unsafe(path):
            return self.not_found(request)
        no_extension = "." not in path.rstrip("/").rsplit("/", 1)[-1]
        spa = path == "/" or path in SPA_PAGES or any(path == p or path.startswith(p + "/") for p in PRACTICE_SPA_PREFIXES)
        if spa and no_extension:
            shell = self.shell()
            return self._send(request, shell) if shell else self.not_found(request)
        if path in PRACTICE_ASSETS or path.startswith(PRACTICE_ASSET_PREFIXES):
            return self._files(request, path)
        return RedirectResponse(main_origin + self._target(request), status_code=302)

    # --- helpers ------------------------------------------------------------------------------------------------

    @staticmethod
    def _path(request: Request) -> str | None:
        """The decoded path, or None for malformed escapes and traversal attempts."""
        raw = request.scope.get("raw_path")
        path = decode_path(raw.decode("latin-1").split("?", 1)[0]) if raw else request.scope["path"]
        return None if path is None or is_unsafe(path) else path

    @staticmethod
    def _target(request: Request) -> str:
        """Path (as sent, still percent-encoded) and query of the request – for redirects to another host."""
        raw = request.scope.get("raw_path")
        target = raw.decode("latin-1").split("?", 1)[0] if raw else request.scope["path"]
        query = request.url.query
        return target + (f"?{query}" if query else "")

    def _files(self, request: Request, path: str) -> Response:
        """Exact landing file → landing directory (308 without slash) → build file → 404."""
        rel = path.lstrip("/")
        found = self._file(self.landing, rel, immutable_ok=False) if rel and not rel.endswith("/") else None
        if found is None and self.landing is not None:
            index_rel = (rel.rstrip("/") + "/index.html").lstrip("/")
            index = self._file(self.landing, index_rel, immutable_ok=False)
            if index is not None:
                if rel and not path.endswith("/"):
                    query = request.url.query
                    return RedirectResponse(path + "/" + (f"?{query}" if query else ""), status_code=308)
                found = index
        if found is None and rel and not rel.endswith("/"):
            found = self._file(self.web, rel, immutable_ok=True)
        if found is None:
            return self.not_found(request)
        return self._send(request, found)

    def not_found(self, request: Request) -> Response:
        page = self._file(self.landing, "404.html", immutable_ok=False)
        if page is not None:
            return Response(page.body, status_code=404, media_type=page.content_type, headers={"Cache-Control": NO_CACHE})
        return problem_response(404, code="not_found")

    @staticmethod
    def _send(request: Request, file: StaticFile) -> Response:
        headers = {"Cache-Control": file.cache_control, "ETag": file.etag}
        if file.csp:
            headers["Content-Security-Policy"] = file.csp  # also on 304: browsers update stored headers from it
        if request.headers.get("if-none-match") == file.etag:
            return Response(status_code=304, headers=headers)
        return Response(file.body, media_type=file.content_type, headers=headers)
