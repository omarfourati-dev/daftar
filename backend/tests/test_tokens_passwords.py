from datetime import UTC, datetime, timedelta

import jwt

from daftar.clock import FixedClock
from daftar.passwords import hash_password, password_problem, verify_password
from daftar.tokens import TokenClaims, Tokens

SECRET = "s" * 40


def test_token_round_trip() -> None:
    tokens = Tokens(SECRET, FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC)))
    assert tokens.verify(tokens.issue(42, 3)) == TokenClaims(user_id=42, token_version=3)


def test_token_expires_after_thirty_days_by_the_injected_clock() -> None:
    clock = FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC))
    tokens = Tokens(SECRET, clock)
    token = tokens.issue(1, 0)
    clock.advance(days=29, hours=23)
    assert tokens.verify(token) is not None
    clock.advance(hours=1)
    assert tokens.verify(token) is None


def test_rejects_foreign_and_broken_tokens() -> None:
    clock = FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC))
    tokens = Tokens(SECRET, clock)
    other = Tokens("o" * 40, clock).issue(1, 0)
    assert tokens.verify(other) is None
    assert tokens.verify("not-a-jwt") is None
    exp = int((clock.now() + timedelta(days=1)).timestamp())
    wrong_issuer = jwt.encode({"iss": "redefluss", "sub": "1", "tv": 0, "exp": exp}, SECRET, algorithm="HS256")
    assert tokens.verify(wrong_issuer) is None
    unsigned = jwt.encode({"iss": "daftar", "sub": "1", "tv": 0, "exp": exp}, None, algorithm="none")
    assert tokens.verify(unsigned) is None


def test_password_hash_round_trip() -> None:
    hashed = hash_password("mot-de-passe-solide")
    assert hashed.startswith("$argon2id$")
    assert verify_password("mot-de-passe-solide", hashed)
    assert not verify_password("mot-de-passe-faux", hashed)
    assert not verify_password("mot-de-passe-solide", "garbage")


def test_password_policy() -> None:
    assert password_problem("123456789") == (
        "password_too_short",
        "Le mot de passe doit contenir au moins 10 caractères.",
    )
    assert password_problem("1234567890") is None
    assert password_problem("x" * 201)[0] == "password_too_long"  # type: ignore[index]
