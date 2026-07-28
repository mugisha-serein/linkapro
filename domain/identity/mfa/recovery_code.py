"""Single-use MFA recovery code model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hmac
import uuid

from .mfa_errors import RecoveryCodeAlreadyUsed


@dataclass(frozen=True)
class RecoveryCode:
    id: uuid.UUID
    code_hash: str
    used_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.code_hash or not self.code_hash.strip():
            raise ValueError("Recovery code hash cannot be empty")
        if self.used_at and (self.used_at.tzinfo is None or self.used_at.utcoffset() is None):
            raise ValueError("Recovery code used time must be timezone-aware")

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def matches(self, presented_hash: str) -> bool:
        return hmac.compare_digest(self.code_hash, presented_hash)

    def consume(self, *, now: datetime) -> "RecoveryCode":
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
        if self.is_used:
            raise RecoveryCodeAlreadyUsed("Recovery code has already been used")
        return RecoveryCode(id=self.id, code_hash=self.code_hash, used_at=now)
