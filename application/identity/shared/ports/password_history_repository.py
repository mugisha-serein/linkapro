"""Password-history persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from domain.identity.credentials import PasswordHash, PasswordHistory


class PasswordHistoryRepository(Protocol):
    def get_password_history(self, user) -> PasswordHistory:
        ...

    def remember_password_hash(self, *, user, password_hash: PasswordHash, now: datetime) -> None:
        ...


__all__ = ["PasswordHistoryRepository"]
