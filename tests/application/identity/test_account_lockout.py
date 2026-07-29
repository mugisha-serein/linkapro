from datetime import datetime, timedelta, timezone

from application.identity.account_lockout import AccountLockoutConfig, AccountLockoutService
from domain.identity.authentication import FailedAttemptCounter


class MemoryAuthenticationAttemptRepository:
    def __init__(self):
        self.counters = {}
        self.saved_ttls = None

    def load_failed_attempt_counter(self, account_key):
        return self.counters.get(account_key, FailedAttemptCounter())

    def save_failed_attempt_counter(
        self,
        account_key,
        counter,
        *,
        observation_window_seconds,
        lock_duration_seconds,
    ):
        self.counters[account_key] = counter
        self.saved_ttls = (observation_window_seconds, lock_duration_seconds)

    def clear_failed_attempt_counter(self, account_key):
        self.counters.pop(account_key, None)


def test_account_lockout_service_persists_failures_and_locks_account():
    repository = MemoryAuthenticationAttemptRepository()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = AccountLockoutService(
        repository=repository,
        config=AccountLockoutConfig(
            max_failures=2,
            observation_window_seconds=900,
            lock_duration_seconds=600,
        ),
        now=lambda: now,
    )

    first = service.record_failure("account-key")
    second = service.record_failure("account-key")

    assert first.locked is False
    assert second.locked is True
    counter = repository.load_failed_attempt_counter("account-key")
    assert len(counter.attempts) == 2
    assert counter.locked_until == now + timedelta(seconds=600)
    assert repository.saved_ttls == (900, 600)


def test_account_lockout_service_resets_on_success():
    repository = MemoryAuthenticationAttemptRepository()
    service = AccountLockoutService(
        repository=repository,
        config=AccountLockoutConfig(
            max_failures=2,
            observation_window_seconds=900,
            lock_duration_seconds=600,
        ),
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    service.record_failure("account-key")
    service.record_success("account-key")

    assert repository.counters == {}
