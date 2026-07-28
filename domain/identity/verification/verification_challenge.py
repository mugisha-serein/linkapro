"""Verification challenge lifecycle."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from domain.identity.shared import AggregateRoot, SystemClock

from .verification_code import VerificationCode
from .verification_errors import (
    InvalidVerificationCode,
    VerificationAttemptLimitExceeded,
    VerificationChallengeConsumed,
    VerificationChallengeExpired,
    VerificationAttemptsExhausted,
    VerificationExpired,
)
from .verification_events import (
    VerificationChallengeExpired as VerificationChallengeExpiredEvent,
    VerificationChallengeIssued,
    VerificationChallengeResent,
    VerificationChallengeSucceeded,
)
from .verification_purpose import VerificationPurpose


_system_clock = SystemClock()


def _now_or_system(now: datetime | None) -> datetime:
    return now if now is not None else _system_clock.now()


@dataclass
class VerificationChallenge(AggregateRoot):
    user_id: uuid.UUID
    purpose: VerificationPurpose
    code_digest: str
    expires_at: datetime
    resend_available_at: datetime
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    issued_at: datetime = field(default_factory=_system_clock.now)
    failed_attempts: int = 0
    max_attempts: int = 5
    succeeded_at: datetime | None = None
    expired_at: datetime | None = None

    @classmethod
    def issue(
        cls,
        *,
        user_id: uuid.UUID,
        purpose: VerificationPurpose | str,
        code: VerificationCode,
        ttl: timedelta,
        resend_cooldown: timedelta,
        max_attempts: int = 5,
        now: datetime | None = None,
    ) -> "VerificationChallenge":
        occurred_at = _now_or_system(now)
        if ttl.total_seconds() <= 0:
            raise ValueError("Verification challenge TTL must be positive")
        if resend_cooldown.total_seconds() < 0:
            raise ValueError("Verification resend cooldown cannot be negative")
        if max_attempts <= 0:
            raise ValueError("Verification max attempts must be positive")
        challenge = cls(
            user_id=user_id,
            purpose=VerificationPurpose(purpose),
            code_digest=code.digest,
            issued_at=occurred_at,
            expires_at=occurred_at + ttl,
            resend_available_at=occurred_at + resend_cooldown,
            max_attempts=max_attempts,
        )
        challenge._record_event(
            VerificationChallengeIssued(
                user_id=user_id,
                challenge_id=challenge.id,
                purpose=challenge.purpose,
                expires_at=challenge.expires_at,
                occurred_at=occurred_at,
            )
        )
        return challenge

    @property
    def is_succeeded(self) -> bool:
        return self.succeeded_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        occurred_at = _now_or_system(now)
        return self.expired_at is not None or occurred_at >= self.expires_at

    def ensure_usable(self, now: datetime | None = None) -> None:
        if self.is_succeeded:
            raise VerificationChallengeConsumed("Verification challenge has already succeeded")
        if self.is_expired(now):
            self.expire(now)
            raise VerificationExpired("Verification challenge has expired")
        if self.failed_attempts >= self.max_attempts:
            raise VerificationAttemptsExhausted("Verification challenge attempt limit exceeded")

    def verify(self, code: VerificationCode, now: datetime | None = None) -> None:
        occurred_at = _now_or_system(now)
        self.ensure_usable(occurred_at)
        if not code.matches_digest(self.code_digest):
            self.failed_attempts += 1
            raise InvalidVerificationCode("Invalid verification code")
        self.succeeded_at = occurred_at
        self._record_event(
            VerificationChallengeSucceeded(
                user_id=self.user_id,
                challenge_id=self.id,
                purpose=self.purpose,
                occurred_at=occurred_at,
            )
        )

    def expire(self, now: datetime | None = None) -> None:
        if self.expired_at is not None:
            return
        occurred_at = _now_or_system(now)
        self.expired_at = occurred_at
        self._record_event(
            VerificationChallengeExpiredEvent(
                user_id=self.user_id,
                challenge_id=self.id,
                purpose=self.purpose,
                occurred_at=occurred_at,
            )
        )

    def mark_resent(self, *, resend_cooldown: timedelta, now: datetime | None = None) -> None:
        occurred_at = _now_or_system(now)
        if resend_cooldown.total_seconds() < 0:
            raise ValueError("Verification resend cooldown cannot be negative")
        self.resend_available_at = occurred_at + resend_cooldown
        self._record_event(
            VerificationChallengeResent(
                user_id=self.user_id,
                challenge_id=self.id,
                purpose=self.purpose,
                resend_available_at=self.resend_available_at,
                occurred_at=occurred_at,
            )
        )
