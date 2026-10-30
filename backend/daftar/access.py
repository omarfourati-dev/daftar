"""Role + subscription guards that ``daftar/deps.py`` does not cover.

- ``OwnerWriter`` – the owner, and the subscription is not suspended (402 otherwise): deleting patients or payments.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from .deps import OwnerUser, Principal, require_writable


def require_owner_writer(user: OwnerUser) -> Principal:
    return require_writable(user)


OwnerWriter = Annotated[Principal, Depends(require_owner_writer)]
