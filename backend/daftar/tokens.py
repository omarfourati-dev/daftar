"""JWT (HS256) for the API. Claims: iss=daftar, sub=user id, tv=token_version, iat, exp (30 days).

Expiry is checked against the injected clock (not the wall clock) so tests can travel in time.
Raising ``token_version`` in the database (password change, "log out everywhere") invalidates every older token.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import jwt

from .clock import Clock

ISSUER = "daftar"
TTL = timedelta(days=30)


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    token_version: int


class Tokens:
    def __init__(self, secret: str, clock: Clock, ttl: timedelta = TTL) -> None:
        self._secret = secret
        self._clock = clock
        self._ttl = ttl

    def issue(self, user_id: int, token_version: int) -> str:
        now = self._clock.now()
        payload = {
            "iss": ISSUER,
            "sub": str(user_id),
            "tv": token_version,
            "iat": int(now.timestamp()),
            "exp": int((now + self._ttl).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify(self, token: str) -> TokenClaims | None:
        """The claims of a valid, unexpired token, else None (never raises)."""
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                issuer=ISSUER,
                options={"verify_exp": False, "verify_iat": False, "require": ["iss", "sub", "tv", "exp"]},
            )
            if int(payload["exp"]) <= self._clock.now().timestamp():
                return None
            return TokenClaims(int(payload["sub"]), int(payload["tv"]))
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None
