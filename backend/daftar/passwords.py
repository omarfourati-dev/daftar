"""Password hashing with Argon2id (argon2-cffi) and the password policy.

Policy (:func:`password_problem`, security review M4): 10 to 200 characters; not one character repeated
(``aaaaaaaaaa``); not a pure run of digits, letters or a keyboard row, forwards or backwards (``1234567890``,
``0987654321``, ``azertyuiop``, ``qwertyuiop`` …); not containing the account's e-mail address or its local part (from
4 characters on – shorter ones would be part of every second password).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH = 10
MAX_LENGTH = 200
#: Runs a password must not be a piece of (lower case; also backwards): digits, the alphabet, keyboard rows of
#: AZERTY (Tunisia, France), QWERTY and QWERTZ.
RUNS = ("0123456789" * 3, "abcdefghijklmnopqrstuvwxyz", "azertyuiop", "qsdfghjklm", "wxcvbn", "qwertyuiop",
        "asdfghjkl", "zxcvbnm", "qwertzuiop", "yxcvbnm")
#: The local part of the e-mail counts from this length on.
MIN_LOCAL_PART = 4

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


def length_problem(password: str) -> tuple[str, str] | None:
    """``(code, detail)`` when the length is not acceptable, else None."""
    if len(password) < MIN_LENGTH:
        return "password_too_short", f"Le mot de passe doit contenir au moins {MIN_LENGTH} caractères."
    if len(password) > MAX_LENGTH:
        return "password_too_long", f"Le mot de passe est trop long (au plus {MAX_LENGTH} caractères)."
    return None


def _is_run(text: str) -> bool:
    return any(text in run or text in run[::-1] for run in RUNS)


def password_problem(password: str, email: str | None = None) -> tuple[str, str] | None:
    """``(code, detail)`` when the password is not acceptable for the account ``email``, else None."""
    if problem := length_problem(password):
        return problem
    lower = password.lower()
    if len(set(lower)) == 1:
        return "password_repeated", "Le mot de passe ne peut pas être un seul caractère répété."
    if _is_run(lower):
        return "password_sequence", "Le mot de passe ne peut pas être une simple suite (1234567890, azertyuiop…)."
    if email:
        address = email.strip().lower()
        local = address.split("@", 1)[0]
        if address in lower or (len(local) >= MIN_LOCAL_PART and local in lower):
            return "password_contains_email", "Le mot de passe ne doit pas contenir votre adresse e-mail."
    return None
