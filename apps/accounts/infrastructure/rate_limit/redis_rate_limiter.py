# No Business Logic Here
from __future__ import annotations

import json
from datetime import datetime, timezone as datetime_timezone
from typing import Any

from django.utils import timezone

from apps.accounts.infrastructure.cache import CacheService


class RedisRateLimiter:
    """
    Cache-backed storage adapter for rate limiting state.

    This class only stores and retrieves raw event snapshots. It does not make
    rate-limit decisions or enforce any policy on its own.
    """

    def __init__(self, prefix: str = "accounts:rate_limit:", cache_service: CacheService | None = None) -> None:
        self.prefix = prefix
        self.cache = cache_service or CacheService()

    def get(self, key: str) -> dict[str, Any] | None:
        payload = self.cache.get(self._key(key))
        if payload is None:
            return None

        if isinstance(payload, dict):
            return payload

        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None

        return None

    def set(self, key: str, value: dict[str, Any], timeout: int | None = None) -> None:
        self.cache.set(self._key(key), value, timeout=timeout)

    def delete(self, key: str) -> None:
        self.cache.delete(self._key(key))

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def serialize_timestamp(self, value: datetime) -> str:
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone=datetime_timezone.utc)
        return value.isoformat()
