"""In-memory sliding-window limits (one process, one container – no Redis needed).

- :class:`LoginThrottle` – like Redefluss: 20 attempts per IP and 5 per e-mail+IP within 15 minutes, counted
  *before* the password hash runs, so a flood cannot burn CPU. A success clears its e-mail+IP bucket. Plus a limit
  per account whatever the IP (security review M4): after 10 failed logins of an e-mail within 15 minutes every
  login of it is refused (429, the right password too) until the oldest failure leaves the window; unknown e-mails
  count the same way, so the answer tells nothing about whether an account exists.
- :class:`RateLimiter` – a generic “N per window and key” limit for demo, pilot requests and other public endpoints.
  Get one per app with ``ctx.limiter(name, limit, window)`` (see daftar/context.py) – never as a module global,
  otherwise tests would share counters.

Both are thread-safe (sync endpoints run in a thread pool) and sweep empty buckets, so memory stays bounded.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timedelta

from .clock import Clock
from .problems import too_many_requests

_SWEEP_EVERY = timedelta(minutes=1)


class _Buckets:
    def __init__(self, clock: Clock, window: timedelta) -> None:
        self.clock = clock
        self.window = window
        self.lock = threading.Lock()
        self.hits: dict[str, deque[datetime]] = {}
        self.last_sweep = clock.now()

    def count(self, key: str, now: datetime) -> int:
        """Hits of ``key`` inside the window; drops expired hits and empty buckets."""
        q = self.hits.get(key)
        if q is None:
            return 0
        while q and q[0] + self.window <= now:
            q.popleft()
        if not q:
            del self.hits[key]
            return 0
        return len(q)

    def add(self, key: str, now: datetime) -> None:
        self.hits.setdefault(key, deque()).append(now)

    def sweep(self, now: datetime, force: bool = False) -> None:
        if not force and now < self.last_sweep + _SWEEP_EVERY:
            return
        self.last_sweep = now
        for key in list(self.hits):
            self.count(key, now)

    def oldest(self, key: str) -> datetime | None:
        q = self.hits.get(key)
        return q[0] if q else None


class LoginThrottle:
    PER_IP = 20
    PER_EMAIL_IP = 5
    PER_KEY = 5
    FAILURES_PER_ACCOUNT = 10
    WINDOW = timedelta(minutes=15)

    def __init__(self, clock: Clock) -> None:
        self._b = _Buckets(clock, self.WINDOW)

    def reserve(self, email: str, ip: str) -> bool:
        """Counts one login attempt; False when the IP or the e-mail+IP pair is over its limit."""
        b = self._b
        with b.lock:
            now = b.clock.now()
            b.sweep(now)
            if b.count(f"i:{ip}", now) >= self.PER_IP or b.count(f"p:{email}|{ip}", now) >= self.PER_EMAIL_IP:
                return False
            b.add(f"i:{ip}", now)
            b.add(f"p:{email}|{ip}", now)
            return True

    def success(self, email: str, ip: str) -> None:
        with self._b.lock:
            self._b.hits.pop(f"p:{email}|{ip}", None)
            self._b.hits.pop(f"a:{email}", None)

    def failure(self, email: str) -> None:
        """Counts a failed login of ``email`` (known or not), from whatever IP."""
        b = self._b
        with b.lock:
            b.add(f"a:{email}", b.clock.now())

    def account_locked(self, email: str) -> bool:
        b = self._b
        with b.lock:
            return b.count(f"a:{email}", b.clock.now()) >= self.FAILURES_PER_ACCOUNT

    def account_retry_after(self, email: str) -> int:
        """Seconds until the oldest failure of ``email`` leaves the window (≥ 1)."""
        b = self._b
        with b.lock:
            now = b.clock.now()
            b.count(f"a:{email}", now)
            oldest = b.oldest(f"a:{email}")
            if oldest is None:
                return 1
            return max(1, int((oldest + self.WINDOW - now).total_seconds()) + 1)

    def reserve_key(self, key: str) -> bool:
        """Single-key variant (5 per 15 min), e.g. password-change guesses per user or invitation tokens per IP."""
        b = self._b
        with b.lock:
            now = b.clock.now()
            b.sweep(now)
            if b.count(f"k:{key}", now) >= self.PER_KEY:
                return False
            b.add(f"k:{key}", now)
            return True

    def clear_key(self, key: str) -> None:
        with self._b.lock:
            self._b.hits.pop(f"k:{key}", None)

    def size(self) -> int:
        with self._b.lock:
            self._b.sweep(self._b.clock.now(), force=True)
            return len(self._b.hits)


class RateLimiter:
    """At most ``limit`` hits per ``window`` and key (key = client IP, or ``""`` for a global limit).

    >>> per_ip = ctx.limiter("demo-ip", 5, timedelta(hours=1))
    >>> per_ip.enforce(ip)          # raises 429 problem+json when over the limit, else counts the hit
    """

    def __init__(self, clock: Clock, limit: int, window: timedelta) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        self.limit = limit
        self.window = window
        self._b = _Buckets(clock, window)

    def allowed(self, key: str = "") -> bool:
        """Peek without counting."""
        b = self._b
        with b.lock:
            return b.count(key, b.clock.now()) < self.limit

    def hit(self, key: str = "") -> bool:
        """Counts a hit and returns True, or returns False (and counts nothing) when the limit is reached."""
        b = self._b
        with b.lock:
            now = b.clock.now()
            b.sweep(now)
            if b.count(key, now) >= self.limit:
                return False
            b.add(key, now)
            return True

    def retry_after(self, key: str = "") -> int:
        """Seconds until the oldest hit of ``key`` leaves the window (≥ 1)."""
        b = self._b
        with b.lock:
            now = b.clock.now()
            b.count(key, now)
            oldest = b.oldest(key)
            if oldest is None:
                return 1
            return max(1, int((oldest + self.window - now).total_seconds()) + 1)

    def enforce(self, key: str = "", detail: str = "Trop de demandes. Veuillez réessayer plus tard.") -> None:
        """Counts a hit or raises ``ApiError(429, code="too_many_requests")`` with ``Retry-After``."""
        if not self.hit(key):
            raise too_many_requests(detail, retry_after=self.retry_after(key))

    def reset(self, key: str | None = None) -> None:
        with self._b.lock:
            if key is None:
                self._b.hits.clear()
            else:
                self._b.hits.pop(key, None)

    def size(self) -> int:
        with self._b.lock:
            self._b.sweep(self._b.clock.now(), force=True)
            return len(self._b.hits)
