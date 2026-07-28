"""Application service for account-level authentication lockout."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Callable, Protocol

from domain.identity.authentication import (
    AccountLockoutDecision,
    AccountLockoutPolicy,
    AuthenticationAttempt,
    FailedAttemptCounter,
)
from domain.identity.shared import SystemClock


class LockoutStateStore(Protocol):
    def get(self, key: str): ...
    def set(self, key: str, value, timeout: int | None = None): ...
    def delete_many(self, keys): ...


@dataclass(frozen=True)
class AccountLockoutConfig:
    max_failures: int
    observation_window_seconds: int
    lock_duration_seconds: int

    def policy(self) -> AccountLockoutPolicy:
        return AccountLockoutPolicy(
            max_failures=self.max_failures,
            observation_window=timedelta(seconds=self.observation_window_seconds),
            lock_duration=timedelta(seconds=self.lock_duration_seconds),
        )


class AccountLockoutService:
    def __init__(
        self,
        *,
        store: LockoutStateStore,
        config: AccountLockoutConfig,
        now: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.config = config
        self.policy = config.policy()
        self.now = now or SystemClock().now

    def is_locked(self, account_key: str | None) -> AccountLockoutDecision:
        if not account_key:
            return AccountLockoutDecision(locked=False, failed_attempts=0)
        now = self.now()
        return self.policy.evaluate(self._load_counter(account_key), now=now)

    def record_failure(self, account_key: str | None) -> AccountLockoutDecision:
        if not account_key:
            return AccountLockoutDecision(locked=False, failed_attempts=0)
        now = self.now()
        counter = self.policy.record_failure(self._load_counter(account_key), now=now)
        self._save_counter(account_key, counter)
        return self.policy.evaluate(counter, now=now)

    def record_success(self, account_key: str | None) -> None:
        if not account_key:
            return
        self.store.delete_many([self._attempts_key(account_key), self._lock_key(account_key)])

    def _load_counter(self, account_key: str) -> FailedAttemptCounter:
        attempts = tuple(
            AuthenticationAttempt(occurred_at=occurred_at, succeeded=False)
            for occurred_at in self._load_attempt_times(account_key)
        )
        locked_until = self._parse_datetime(self.store.get(self._lock_key(account_key)))
        return FailedAttemptCounter(attempts=attempts, locked_until=locked_until)

    def _save_counter(self, account_key: str, counter: FailedAttemptCounter) -> None:
        attempt_times = [
            attempt.occurred_at.isoformat()
            for attempt in counter.attempts
            if not attempt.succeeded
        ]
        self.store.set(
            self._attempts_key(account_key),
            attempt_times,
            timeout=self._ttl(self.config.observation_window_seconds),
        )
        if counter.locked_until:
            self.store.set(
                self._lock_key(account_key),
                counter.locked_until.isoformat(),
                timeout=self._ttl(self.config.lock_duration_seconds),
            )

    def _load_attempt_times(self, account_key: str) -> tuple[datetime, ...]:
        raw_attempts = self.store.get(self._attempts_key(account_key)) or []
        if isinstance(raw_attempts, int):
            return tuple(self.now() for _ in range(raw_attempts))
        if not isinstance(raw_attempts, (list, tuple)):
            return ()
        return tuple(
            parsed
            for value in raw_attempts
            if (parsed := self._parse_datetime(value)) is not None
        )

    @staticmethod
    def _parse_datetime(value) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed

    @staticmethod
    def _ttl(seconds: int) -> int:
        return max(ceil(seconds), 1)

    @staticmethod
    def _attempts_key(account_key: str) -> str:
        return f"login_fail:{account_key}"

    @staticmethod
    def _lock_key(account_key: str) -> str:
        return f"login_lock:{account_key}"
