"""Authentication failed-attempt persistence port."""

from typing import Protocol

from domain.identity.authentication import FailedAttemptCounter


class AuthenticationAttemptRepository(Protocol):
    def load_failed_attempt_counter(self, account_key: str) -> FailedAttemptCounter:
        ...

    def save_failed_attempt_counter(
        self,
        account_key: str,
        counter: FailedAttemptCounter,
        *,
        observation_window_seconds: int,
        lock_duration_seconds: int,
    ) -> None:
        ...

    def clear_failed_attempt_counter(self, account_key: str) -> None:
        ...


__all__ = ["AuthenticationAttemptRepository"]
