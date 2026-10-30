"""Password hashing with Argon2id (argon2-cffi) and the password policy (≥ 10 characters)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 10
MAX_LENGTH = 200

# OWASP minimum for Argon2id (19 MiB, t=2, p=1): cheap enough for a 384 MB container, still memory-hard.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)


def use_hasher(hasher: PasswordHasher) -> None:
    """Tests swap in a cheap hasher (see tests/conftest.py)."""
    global _hasher, _dummy
    _hasher = hasher
    _dummy = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


_dummy: str | None = None


def verify_against_dummy(password: str) -> None:
    """Burns the same time as a real check, so unknown e-mails are not faster than wrong passwords."""
    global _dummy
    if _dummy is None:
        _dummy = _hasher.hash("dummy-password-for-timing")
    verify_password(password, _dummy)


def password_problem(password: str) -> tuple[str, str] | None:
    """``(code, detail)`` when the password is not acceptable, else None."""
    if len(password) < MIN_LENGTH:
        return "password_too_short", f"Le mot de passe doit contenir au moins {MIN_LENGTH} caractères."
    if len(password) > MAX_LENGTH:
        return "password_too_long", f"Le mot de passe est trop long (au plus {MAX_LENGTH} caractères)."
    return None
