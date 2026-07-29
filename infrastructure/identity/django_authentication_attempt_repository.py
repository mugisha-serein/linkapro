"""Django cache-backed authentication attempt repository."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from math import ceil

from django.conf import settings
from django.core.cache import cache

from application.identity.shared.ports import AuthenticationAttemptRepository
from domain.identity.authentication import AuthenticationAttempt, FailedAttemptCounter


class DjangoAuthenticationAttemptRepository(AuthenticationAttemptRepository):
    def load_failed_attempt_counter(self, account_key: str) -> FailedAttemptCounter:
        attempts = tuple(
            AuthenticationAttempt(occurred_at=occurred_at, succeeded=False)
            for occurred_at in self._load_attempt_times(account_key)
        )
        locked_until = self._parse_datetime(cache.get(self._lock_key(account_key)))
        return FailedAttemptCounter(attempts=attempts, locked_until=locked_until)

    def save_failed_attempt_counter(
        self,
        account_key: str,
        counter: FailedAttemptCounter,
        *,
        observation_window_seconds: int,
        lock_duration_seconds: int,
    ) -> None:
        attempt_times = [
            attempt.occurred_at.isoformat()
            for attempt in counter.attempts
            if not attempt.succeeded
        ]
        cache.set(
            self._attempts_key(account_key),
            attempt_times,
            timeout=self._ttl(observation_window_seconds),
        )
        if counter.locked_until:
            cache.set(
                self._lock_key(account_key),
                counter.locked_until.isoformat(),
                timeout=self._ttl(lock_duration_seconds),
            )

    def clear_failed_attempt_counter(self, account_key: str) -> None:
        cache.delete_many([self._attempts_key(account_key), self._lock_key(account_key)])

    def _load_attempt_times(self, account_key: str) -> tuple[datetime, ...]:
        raw_attempts = cache.get(self._attempts_key(account_key)) or []
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

    def _attempts_key(self, account_key: str) -> str:
        return f"login_fail:{self._safe_account_key(account_key)}"

    def _lock_key(self, account_key: str) -> str:
        return f"login_lock:{self._safe_account_key(account_key)}"

    @staticmethod
    def _safe_account_key(account_key: str) -> str:
        key = str(getattr(settings, "RATE_LIMIT_HASH_KEY", "") or settings.SECRET_KEY).encode("utf-8")
        return hmac.new(key, account_key.encode("utf-8"), hashlib.sha256).hexdigest()


__all__ = ["DjangoAuthenticationAttemptRepository"]
