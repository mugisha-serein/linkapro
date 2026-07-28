"""MFA challenge entity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from .mfa_method import MfaMethod
from .mfa_errors import MfaChallengeExpired


@dataclass(frozen=True)
class MfaChallenge:
    id: uuid.UUID
    user_id: uuid.UUID
    method: MfaMethod
    issued_at: datetime
    expires_at: datetime
    max_attempts: int
    attempt_count: int = 0
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.issued_at.tzinfo is None or self.issued_at.utcoffset() is None:
            raise ValueError("MFA challenge issue time must be timezone-aware")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("MFA challenge expiry time must be timezone-aware")
        if self.expires_at <= self.issued_at:
            raise ValueError("MFA challenge must expire after it is issued")
        if self.max_attempts <= 0:
            raise ValueError("MFA challenge max_attempts must be positive")
        if self.attempt_count < 0:
            raise ValueError("MFA challenge attempt_count cannot be negative")
        if self.consumed_at and (
            self.consumed_at.tzinfo is None or self.consumed_at.utcoffset() is None
        ):
            raise ValueError("MFA challenge consumed time must be timezone-aware")

    def is_expired(self, *, now: datetime) -> bool:
        self._validate_now(now)
        return now >= self.expires_at

    def attempts_exhausted(self) -> bool:
        return self.attempt_count >= self.max_attempts

    def can_attempt(self, *, now: datetime) -> bool:
        if self.is_expired(now=now):
            raise MfaChallengeExpired("MFA challenge has expired")
        return (
            self.consumed_at is None
            and not self.attempts_exhausted()
        )

    def record_failed_attempt(self) -> "MfaChallenge":
        return MfaChallenge(
            id=self.id,
            user_id=self.user_id,
            method=self.method,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            max_attempts=self.max_attempts,
            attempt_count=self.attempt_count + 1,
            consumed_at=self.consumed_at,
        )

    def consume(self, *, now: datetime) -> "MfaChallenge":
        self._validate_now(now)
        return MfaChallenge(
            id=self.id,
            user_id=self.user_id,
            method=self.method,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            max_attempts=self.max_attempts,
            attempt_count=self.attempt_count + 1,
            consumed_at=now,
        )

    @staticmethod
    def _validate_now(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
