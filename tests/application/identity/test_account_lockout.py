from datetime import datetime, timedelta, timezone

from application.identity.account_lockout import AccountLockoutConfig, AccountLockoutService


class MemoryStore:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, timeout=None):
        self.values[key] = value

    def delete_many(self, keys):
        for key in keys:
            self.values.pop(key, None)


def test_account_lockout_service_persists_failures_and_locks_account():
    store = MemoryStore()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = AccountLockoutService(
        store=store,
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
    assert len(store.values["login_fail:account-key"]) == 2
    assert store.values["login_lock:account-key"] == (now + timedelta(seconds=600)).isoformat()


def test_account_lockout_service_resets_on_success():
    store = MemoryStore()
    service = AccountLockoutService(
        store=store,
        config=AccountLockoutConfig(
            max_failures=2,
            observation_window_seconds=900,
            lock_duration_seconds=600,
        ),
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    service.record_failure("account-key")
    service.record_success("account-key")

    assert store.values == {}
