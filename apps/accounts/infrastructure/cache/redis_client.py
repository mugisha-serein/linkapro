# No Business Logic Here
from __future__ import annotations

from typing import Any

from django.core.cache import caches


class RedisClient:
    """
    Thin cache backend wrapper.

    This adapter only forwards raw cache operations to Django's configured
    cache backend. It does not interpret the stored data.
    """

    def __init__(self, alias: str = "default") -> None:
        self.alias = alias
        try:
            self._cache = caches[alias]
            self.available = True
        except Exception:
            self._cache = None
            self.available = False

    def get(self, key: str, default: Any | None = None) -> Any | None:
        self._require_cache()
        return self._cache.get(key, default)

    def set(self, key: str, value: Any, timeout: int | None = None) -> bool:
        self._require_cache()
        return self._cache.set(key, value, timeout=timeout)

    def delete(self, key: str) -> bool:
        self._require_cache()
        return self._cache.delete(key)

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        self._require_cache()
        return self._cache.get_many(keys)

    def set_many(self, data: dict[str, Any], timeout: int | None = None) -> list[str]:
        self._require_cache()
        return self._cache.set_many(data, timeout=timeout)

    def delete_many(self, keys: list[str]) -> None:
        self._require_cache()
        self._cache.delete_many(keys)

    def clear(self) -> None:
        self._require_cache()
        self._cache.clear()

    def _require_cache(self):
        if self._cache is None:
            raise RuntimeError(f"Cache backend '{self.alias}' is unavailable.")
        return self._cache

