# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from uuid import uuid4
from typing import Any

from django.utils import timezone

from apps.accounts.infrastructure.cache import CacheService


@dataclass(slots=True)
class RedisHealthCheckResult:
    healthy: bool
    backend: str
    checked_at: datetime
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


class RedisHealthCheck:
    """
    Infrastructure observability probe for cache/Redis availability.

    The probe performs a raw set/get/delete round-trip through the cache
    abstraction and reports the result without making any application-level
    decisions.
    """

    def __init__(self, cache_service: CacheService | None = None, probe_ttl_seconds: int = 10) -> None:
        self.cache = cache_service or CacheService()
        self.probe_ttl_seconds = probe_ttl_seconds

    def check(self) -> RedisHealthCheckResult:
        checked_at = timezone.now()
        probe_key = f"accounts:monitoring:redis_health:{uuid4().hex}"
        probe_value = {"checked_at": checked_at.isoformat()}
        started = perf_counter()

        try:
            write_ok = self.cache.set(probe_key, probe_value, timeout=self.probe_ttl_seconds)
            cached_value = self.cache.get(probe_key)
            self.cache.delete(probe_key)
            elapsed_ms = (perf_counter() - started) * 1000.0

            healthy = bool(write_ok) and cached_value == probe_value
            details = {
                "write_ok": bool(write_ok),
                "read_back": cached_value is not None,
                "probe_key": probe_key,
            }
            if cached_value != probe_value:
                details["mismatch"] = True

            return RedisHealthCheckResult(
                healthy=healthy,
                backend=type(self.cache.redis_client).__name__,
                checked_at=checked_at,
                latency_ms=elapsed_ms,
                details=details,
            )
        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000.0
            return RedisHealthCheckResult(
                healthy=False,
                backend=type(self.cache.redis_client).__name__,
                checked_at=checked_at,
                latency_ms=elapsed_ms,
                details={
                    "error": exc.__class__.__name__,
                    "message": str(exc),
                    "probe_key": probe_key,
                },
            )

