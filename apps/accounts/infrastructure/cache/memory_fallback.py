# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from time import monotonic
from typing import Any


@dataclass(slots=True)
class _MemoryCacheEntry:
    value: Any
    expires_at: float | None


@dataclass(slots=True)
class MemoryCacheFallback:
    """
    In-memory cache fallback.

    The fallback stores raw values and optional expiry timestamps. It is meant
    for local/dev use or as a temporary fallback when the primary cache backend
    is unavailable.
    """

    _store: dict[str, _MemoryCacheEntry] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return default
            if entry.expires_at is not None and monotonic() >= entry.expires_at:
                self._store.pop(key, None)
                return default
            return entry.value

    def set(self, key: str, value: Any, timeout: int | None = None) -> bool:
        with self._lock:
            self._store[key] = _MemoryCacheEntry(value=value, expires_at=self._expires_at(timeout))
        return True

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
        return existed

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        return {key: value for key in keys if (value := self.get(key, default=None)) is not None}

    def set_many(self, data: dict[str, Any], timeout: int | None = None) -> list[str]:
        with self._lock:
            for key, value in data.items():
                self._store[key] = _MemoryCacheEntry(value=value, expires_at=self._expires_at(timeout))
        return []

    def delete_many(self, keys: list[str]) -> None:
        with self._lock:
            for key in keys:
                self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _expires_at(self, timeout: int | None) -> float | None:
        if timeout is None:
            return None
        if timeout <= 0:
            return monotonic()
        return monotonic() + timeout

