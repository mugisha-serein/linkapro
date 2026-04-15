# No Business Logic Here
from __future__ import annotations

from typing import Any

from apps.accounts.infrastructure.cache.memory_fallback import MemoryCacheFallback
from apps.accounts.infrastructure.cache.redis_client import RedisClient


class CacheService:
    """
    Unified cache interface.

    It tries the configured cache backend first and falls back to the local
    in-memory store if the backend is unavailable or raises an exception.
    """

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        fallback: MemoryCacheFallback | None = None,
        prefer_redis: bool = True,
    ) -> None:
        self.redis_client = redis_client or RedisClient()
        self.fallback = fallback or MemoryCacheFallback()
        self.prefer_redis = prefer_redis

    def get(self, key: str, default: Any | None = None) -> Any | None:
        try:
            if self.prefer_redis and self.redis_client.available:
                return self.redis_client.get(key, default)
        except Exception:
            pass
        return self.fallback.get(key, default)

    def set(self, key: str, value: Any, timeout: int | None = None) -> bool:
        try:
            if self.prefer_redis and self.redis_client.available:
                return bool(self.redis_client.set(key, value, timeout=timeout))
        except Exception:
            pass
        return self.fallback.set(key, value, timeout=timeout)

    def delete(self, key: str) -> bool:
        try:
            if self.prefer_redis and self.redis_client.available:
                return bool(self.redis_client.delete(key))
        except Exception:
            pass
        return self.fallback.delete(key)

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        try:
            if self.prefer_redis and self.redis_client.available:
                return self.redis_client.get_many(keys)
        except Exception:
            pass
        return self.fallback.get_many(keys)

    def set_many(self, data: dict[str, Any], timeout: int | None = None) -> list[str]:
        try:
            if self.prefer_redis and self.redis_client.available:
                return self.redis_client.set_many(data, timeout=timeout)
        except Exception:
            pass
        return self.fallback.set_many(data, timeout=timeout)

    def delete_many(self, keys: list[str]) -> None:
        try:
            if self.prefer_redis and self.redis_client.available:
                self.redis_client.delete_many(keys)
                return
        except Exception:
            pass
        self.fallback.delete_many(keys)

    def clear(self) -> None:
        try:
            if self.prefer_redis and self.redis_client.available:
                self.redis_client.clear()
                return
        except Exception:
            pass
        self.fallback.clear()

