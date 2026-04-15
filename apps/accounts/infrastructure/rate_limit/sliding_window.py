# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.utils import timezone

from apps.accounts.infrastructure.rate_limit.redis_rate_limiter import RedisRateLimiter


@dataclass(slots=True)
class SlidingWindowRateLimitResult:
    allowed: bool
    current_count: int
    limit: int
    retry_after_seconds: int
    window_started_at: datetime
    window_ends_at: datetime
    evaluated_at: datetime


class SlidingWindowRateLimiter:
    """
    Sliding-window traffic control backed by cache storage.

    The limiter stores raw timestamps and trims them to the configured window.
    It does not know anything about authentication, users, or permissions.
    """

    def __init__(self, storage: RedisRateLimiter | None = None) -> None:
        self.storage = storage or RedisRateLimiter()

    def allow(self, key: str, limit: int, window_seconds: int, now: datetime | None = None) -> SlidingWindowRateLimitResult:
        evaluated_at = now or timezone.now()
        window_started_at = evaluated_at - timedelta(seconds=window_seconds)
        window_ends_at = evaluated_at

        snapshot = self.storage.get(key) or {}
        raw_events = snapshot.get("events", [])
        events = [self._parse_timestamp(value) for value in raw_events]
        events = [event for event in events if event >= window_started_at]

        current_count = len(events)
        if current_count >= limit:
            retry_after_seconds = self._retry_after_seconds(events, evaluated_at, window_seconds)
            self.storage.set(
                key,
                {"events": [event.isoformat() for event in events]},
                timeout=window_seconds,
            )
            return SlidingWindowRateLimitResult(
                allowed=False,
                current_count=current_count,
                limit=limit,
                retry_after_seconds=retry_after_seconds,
                window_started_at=window_started_at,
                window_ends_at=window_ends_at,
                evaluated_at=evaluated_at,
            )

        events.append(evaluated_at)
        self.storage.set(
            key,
            {"events": [event.isoformat() for event in events]},
            timeout=window_seconds,
        )
        return SlidingWindowRateLimitResult(
            allowed=True,
            current_count=current_count + 1,
            limit=limit,
            retry_after_seconds=0,
            window_started_at=window_started_at,
            window_ends_at=window_ends_at,
            evaluated_at=evaluated_at,
        )

    def clear(self, key: str) -> None:
        self.storage.delete(key)

    def _parse_timestamp(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone=datetime_timezone.utc)
        return parsed

    def _retry_after_seconds(self, events: list[datetime], now: datetime, window_seconds: int) -> int:
        if not events:
            return 0
        oldest_event = min(events)
        retry_at = oldest_event + timedelta(seconds=window_seconds)
        return max(int((retry_at - now).total_seconds()), 0)
