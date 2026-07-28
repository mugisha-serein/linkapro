"""Pure failed-attempt counter for authentication lockout policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .authentication_attempt import AuthenticationAttempt


@dataclass(frozen=True)
class FailedAttemptCounter:
    attempts: tuple[AuthenticationAttempt, ...] = field(default_factory=tuple)
    locked_until: datetime | None = None

    def failures_within(self, *, window: timedelta, now: datetime) -> tuple[AuthenticationAttempt, ...]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
        cutoff = now - window
        return tuple(
            attempt
            for attempt in self.attempts
            if not attempt.succeeded and attempt.occurred_at >= cutoff
        )

    def record_failure(self, *, window: timedelta, now: datetime) -> "FailedAttemptCounter":
        failures = self.failures_within(window=window, now=now)
        return FailedAttemptCounter(
            attempts=failures + (AuthenticationAttempt(occurred_at=now, succeeded=False),),
            locked_until=self.locked_until,
        )

    def reset_on_success(self) -> "FailedAttemptCounter":
        return FailedAttemptCounter()
