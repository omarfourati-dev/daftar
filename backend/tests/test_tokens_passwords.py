from datetime import UTC, datetime, timedelta

import jwt
import pytest

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
    assert password_problem("mot-de-passe") is None
    assert password_problem("x" * 201)[0] == "password_too_long"  # type: ignore[index]


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("aaaaaaaaaa", "password_repeated"),
        ("0000000000000", "password_repeated"),
        ("1234567890", "password_sequence"),
        ("0987654321", "password_sequence"),
        ("123456789012", "password_sequence"),  # on and on
        ("azertyuiop", "password_sequence"),
        ("AZERTYUIOP", "password_sequence"),
        ("qwertyuiop", "password_sequence"),
        ("poiuytreza", "password_sequence"),
        ("qwertzuiop", "password_sequence"),
        ("abcdefghijk", "password_sequence"),
        ("qsdfghjklm", "password_sequence"),
        ("1234567890a", None),  # not only a sequence
        ("azerty-2026-tunis", None),
        ("mot-de-passe-solide", None),
    ],
)
def test_password_policy_refuses_what_is_guessed_first(password: str, code: str | None) -> None:
    """Security review M4: besides the length, no single repeated character and no pure digit or keyboard run."""
    problem = password_problem(password)
    assert (problem[0] if problem else None) == code


def test_password_must_not_contain_the_email() -> None:
    assert password_problem("amira.bensalah-2026", "Amira.BenSalah@cabinet.tn")[0] == "password_contains_email"  # type: ignore[index]
    assert password_problem("x-amira.bensalah@cabinet.tn", "amira.bensalah@cabinet.tn")[0] == "password_contains_email"  # type: ignore[index]
    assert password_problem("MON-CABINET-SAMI-2026", "sami@cabinet.tn")[0] == "password_contains_email"  # type: ignore[index]
    assert password_problem("dr-ab-mot-de-passe", "ab@cabinet.tn") is None  # a local part this short is everywhere
    assert password_problem("mot-de-passe-solide", "sami@cabinet.tn") is None
    assert password_problem("mot-de-passe-solide", None) is None
