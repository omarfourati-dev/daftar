"""Per-app services, reachable in every handler through the ``Ctx`` dependency (``request.app.state.ctx``).

Nothing in here is a module global: each ``create_app`` builds its own context, so tests are isolated.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import Engine

from .clock import Clock
from .metrics import Metrics
from .settings import Settings
from .throttle import LoginThrottle, RateLimiter
from .tokens import Tokens


@dataclass
class AppContext:
    settings: Settings
    clock: Clock
    engine: Engine
    metrics: Metrics
    tokens: Tokens
    login_throttle: LoginThrottle
    _limiters: dict[str, RateLimiter] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def limiter(self, name: str, limit: int, window: timedelta) -> RateLimiter:
        """The app-wide limiter ``name`` (created on first use; later calls return the same one).

        ``ctx.limiter("demo-ip", 5, timedelta(hours=1)).enforce(ip)``
        """
        with self._lock:
            existing = self._limiters.get(name)
            if existing is None:
                existing = RateLimiter(self.clock, limit, window)
                self._limiters[name] = existing
            elif existing.limit != limit or existing.window != window:
                raise ValueError(f"limiter {name!r} already exists with other limits")
            return existing
