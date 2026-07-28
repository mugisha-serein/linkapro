"""Pure account-level lockout policy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .failed_attempt_counter import FailedAttemptCounter


@dataclass(frozen=True)
class AccountLockoutDecision:
    locked: bool
    failed_attempts: int
    locked_until: datetime | None = None


@dataclass(frozen=True)
class AccountLockoutPolicy:
    max_failures: int
    observation_window: timedelta
    lock_duration: timedelta

    def __post_init__(self) -> None:
        if self.max_failures <= 0:
            raise ValueError("max_failures must be positive")
        if self.observation_window.total_seconds() <= 0:
            raise ValueError("observation_window must be positive")
        if self.lock_duration.total_seconds() <= 0:
            raise ValueError("lock_duration must be positive")

    def evaluate(self, counter: FailedAttemptCounter, *, now: datetime) -> AccountLockoutDecision:
        self._validate_now(now)
        if counter.locked_until and counter.locked_until > now:
            return AccountLockoutDecision(
                locked=True,
                failed_attempts=len(counter.failures_within(window=self.observation_window, now=now)),
                locked_until=counter.locked_until,
            )
        failures = counter.failures_within(window=self.observation_window, now=now)
        return AccountLockoutDecision(locked=False, failed_attempts=len(failures))

    def record_failure(self, counter: FailedAttemptCounter, *, now: datetime) -> FailedAttemptCounter:
        self._validate_now(now)
        current = self.evaluate(counter, now=now)
        if current.locked:
            return counter

        updated = counter.record_failure(window=self.observation_window, now=now)
        if len(updated.failures_within(window=self.observation_window, now=now)) >= self.max_failures:
            return FailedAttemptCounter(
                attempts=updated.failures_within(window=self.observation_window, now=now),
                locked_until=now + self.lock_duration,
            )
        return updated

    def record_success(self, counter: FailedAttemptCounter) -> FailedAttemptCounter:
        return counter.reset_on_success()

    @staticmethod
    def _validate_now(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
