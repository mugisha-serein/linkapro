"""Application service for account-level authentication lockout."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from domain.identity.authentication import (
    AccountLockoutDecision,
    AccountLockoutPolicy,
)
from domain.identity.shared import SystemClock

from application.identity.shared.ports import AuthenticationAttemptRepository


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
        repository: AuthenticationAttemptRepository,
        config: AccountLockoutConfig,
        now: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self.config = config
        self.policy = config.policy()
        self.now = now or SystemClock().now

    def is_locked(self, account_key: str | None) -> AccountLockoutDecision:
        if not account_key:
            return AccountLockoutDecision(locked=False, failed_attempts=0)
        now = self.now()
        return self.policy.evaluate(
            self.repository.load_failed_attempt_counter(account_key),
            now=now,
        )

    def record_failure(self, account_key: str | None) -> AccountLockoutDecision:
        if not account_key:
            return AccountLockoutDecision(locked=False, failed_attempts=0)
        now = self.now()
        counter = self.policy.record_failure(
            self.repository.load_failed_attempt_counter(account_key),
            now=now,
        )
        self.repository.save_failed_attempt_counter(
            account_key,
            counter,
            observation_window_seconds=self.config.observation_window_seconds,
            lock_duration_seconds=self.config.lock_duration_seconds,
        )
        return self.policy.evaluate(counter, now=now)

    def record_success(self, account_key: str | None) -> None:
        if not account_key:
            return
        self.repository.clear_failed_attempt_counter(account_key)
