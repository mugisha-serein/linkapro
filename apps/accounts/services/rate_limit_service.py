import uuid
import time
import json
import redis
from django.conf import settings


class RedisSlidingWindowRateLimiter:
    """
    Implements a Redis-backed sliding window rate limiter.
    """

    PREFIX = 'rate_limit:'

    def __init__(self):
        self.redis_client = None
        self._memory_store = {}
        self._redis_available = False

        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.redis_client.ping()
            self._redis_available = True
        except (redis.ConnectionError, redis.TimeoutError):
            self.redis_client = None
            self._redis_available = False

    def _key(self, name, identifier):
        identifier = str(identifier).strip().lower()
        return f"{self.PREFIX}{name}:{identifier}"

    def is_allowed(self, name, identifier, limit, period_seconds):
        key = self._key(name, identifier)
        now = int(time.time())
        window_start = now - period_seconds
        member = f"{now}:{uuid.uuid4()}"

        if self._redis_available and self.redis_client:
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, period_seconds + 1)
            _, _, count, _ = pipe.execute()
            return count <= limit

        # In-memory fallback for local development/testing
        values = self._memory_store.get(key, [])
        values = [timestamp for timestamp in values if timestamp > window_start]
        values.append(now)
        self._memory_store[key] = values
        return len(values) <= limit


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


rate_limiter = RedisSlidingWindowRateLimiter()