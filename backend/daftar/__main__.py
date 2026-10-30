"""``python -m daftar`` – starts the server (run ``alembic upgrade head`` before)."""

from __future__ import annotations

import logging
import sys

import uvicorn

from .app import create_app
from .settings import Settings, SettingsError


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
    try:
        settings = Settings.from_env()
    except SettingsError as exc:
        logging.getLogger("daftar").error("configuration: %s", exc)
        raise SystemExit(1) from exc
    logging.getLogger("daftar").info("starting with %r", settings)
    app = create_app(settings)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=False,  # the real client IP comes from X-Forwarded-For (see deps.client_ip)
        access_log=False,  # daftar.http logs every request without the query string
        log_config=None,
        timeout_graceful_shutdown=20,
    )


if __name__ == "__main__":
    main()
