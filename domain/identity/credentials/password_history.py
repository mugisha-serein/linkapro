"""Password reuse prevention."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable

from .password_hash import PasswordHash
from .plain_password import PlainPassword


from domain.identity.shared import DomainError


class PasswordReuseNotAllowed(DomainError):
    pass


PasswordReuseError = PasswordReuseNotAllowed


PasswordVerifier = Callable[[PlainPassword, PasswordHash], bool]


@dataclass(frozen=True)
class PasswordHistoryEntry:
    password_hash: PasswordHash
    changed_at: datetime | None = None


@dataclass(frozen=True)
class PasswordHistory:
    entries: tuple[PasswordHistoryEntry, ...] = field(default_factory=tuple)
    max_entries: int = 5

    def __init__(
        self,
        entries: Iterable[PasswordHistoryEntry | PasswordHash] = (),
        *,
        max_entries: int = 5,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("Password history size must be positive")
        normalized_entries = tuple(
            entry if isinstance(entry, PasswordHistoryEntry) else PasswordHistoryEntry(entry)
            for entry in entries
        )
        object.__setattr__(self, "entries", normalized_entries[:max_entries])
        object.__setattr__(self, "max_entries", max_entries)

    def ensure_not_reused(self, candidate: PlainPassword, verifier: PasswordVerifier) -> None:
        for entry in self.entries:
            if verifier(candidate, entry.password_hash):
                raise PasswordReuseError("Password was used recently")

    def record(self, password_hash: PasswordHash, *, changed_at: datetime | None = None) -> "PasswordHistory":
        return PasswordHistory(
            (PasswordHistoryEntry(password_hash, changed_at), *self.entries),
            max_entries=self.max_entries,
        )
