"""Configuration from environment variables (12-factor). `repr()` never shows a secret."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
MIN_JWT_SECRET = 32


class SettingsError(ValueError):
    """A required variable is missing or invalid; the app refuses to start."""


def normalize_database_url(url: str) -> str:
    """Accepts postgres://, postgresql:// and postgresql+psycopg:// and always returns the psycopg 3 form."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    if not url.startswith("postgresql+psycopg://"):
        raise SettingsError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg://user:password@host:port/db)")
    return url


@dataclass(frozen=True, repr=False)
class Settings:
    database_url: str
    jwt_secret: str
    admin_email: str | None = None
    admin_password: str | None = None
    admin_reset_password: bool = False
    port: int = 8080
    #: Static marketing site (exact files and directories with index.html).
    landing_dir: Path = field(default_factory=lambda: REPO_ROOT / "landing")
    #: SvelteKit build output (adapter-static, contains 200.html).
    web_dir: Path = field(default_factory=lambda: REPO_ROOT / "web" / "build")
    #: One line per request (method, path without query, status, duration) on stdout.
    log_requests: bool = True
    #: Main domain; practices live on ``<slug>.<base_domain>`` (booking page and their own app).
    base_domain: str = "daftar.omarfourati.de"
    #: Flouci payment keys (section 11.4); without them online payment is switched off.
    flouci_app_token: str | None = None
    flouci_app_secret: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "database_url", normalize_database_url(self.database_url))
        if len(self.jwt_secret) < MIN_JWT_SECRET:
            raise SettingsError(f"JWT_SECRET must have at least {MIN_JWT_SECRET} characters")
        if self.admin_email is not None:
            object.__setattr__(self, "admin_email", self.admin_email.strip().lower() or None)
        object.__setattr__(self, "base_domain", self.base_domain.strip().lower().strip("."))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        def opt(name: str) -> str | None:
            value = env.get(name, "").strip()
            return value or None

        def req(name: str) -> str:
            value = opt(name)
            if value is None:
                raise SettingsError(f"{name} is missing")
            return value

        port_text = opt("PORT") or "8080"
        if not port_text.isdigit() or not 0 < int(port_text) < 65536:
            raise SettingsError("PORT must be a number between 1 and 65535")
        extra: dict[str, Path] = {}
        if landing := opt("LANDING_DIR"):
            extra["landing_dir"] = Path(landing)
        if web := opt("WEB_DIR"):
            extra["web_dir"] = Path(web)
        return cls(
            database_url=req("DATABASE_URL"),
            jwt_secret=req("JWT_SECRET"),
            admin_email=opt("ADMIN_EMAIL"),
            admin_password=opt("ADMIN_PASSWORD"),
            admin_reset_password=(opt("ADMIN_RESET_PASSWORD") or "").lower() in {"1", "true", "yes"},
            port=int(port_text),
            log_requests=(opt("LOG_REQUESTS") or "true").lower() not in {"0", "false", "no"},
            base_domain=opt("BASE_DOMAIN") or "daftar.omarfourati.de",
            flouci_app_token=opt("FLOUCI_APP_TOKEN"),
            flouci_app_secret=opt("FLOUCI_APP_SECRET"),
            **extra,
        )

    def __repr__(self) -> str:
        url = make_url(self.database_url).render_as_string(hide_password=True)
        return (
            f"Settings(database_url={url!r}, jwt_secret='***', admin_email={self.admin_email!r}, "
            f"admin_password={'***' if self.admin_password else None!r}, "
            f"admin_reset_password={self.admin_reset_password}, port={self.port}, "
            f"landing_dir={str(self.landing_dir)!r}, web_dir={str(self.web_dir)!r}, log_requests={self.log_requests}, "
            f"base_domain={self.base_domain!r}, flouci_app_token={'***' if self.flouci_app_token else None!r}, "
            f"flouci_app_secret={'***' if self.flouci_app_secret else None!r})"
        )

    __str__ = __repr__
