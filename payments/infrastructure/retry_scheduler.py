import logging

from celery import current_app
import redis

from django_app.common.redis_config import get_redis_client
from payments.application.ports import IRetryScheduler

logger = logging.getLogger(__name__)


class CeleryRetryScheduler(IRetryScheduler):
    def __init__(self, redis_client: redis.Redis | None = None, max_attempts: int = 3, retry_ttl_seconds: int = 3600):
        self._redis_client = redis_client
        self.max_attempts = max_attempts
        self.retry_ttl_seconds = retry_ttl_seconds

    @property
    def redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = get_redis_client()
        return self._redis_client

    def _retry_key(self, provider_reference: str) -> str:
        return f"payment_webhook_retry:{provider_reference}"

    def schedule_webhook_retry(self, provider_reference: str, delay_seconds: int) -> None:
        key = self._retry_key(provider_reference)
        attempt = int(self.redis_client.incr(key))
        if attempt == 1:
            self.redis_client.expire(key, self.retry_ttl_seconds)
        if attempt > self.max_attempts:
            logger.warning(
                "payment_webhook_retry_exhausted",
                extra={"provider_reference": provider_reference, "attempt": attempt, "max_attempts": self.max_attempts},
            )
            return

        current_app.send_task(
            "payments.tasks.process_webhook_retry",
            args=[provider_reference],
            countdown=delay_seconds,
        )

        logger.info(
            "payment_webhook_retry_scheduled",
            extra={"provider_reference": provider_reference, "attempt": attempt, "delay_seconds": delay_seconds},
        )

    def reset_webhook_retry(self, provider_reference: str) -> None:
        self.redis_client.delete(self._retry_key(provider_reference))
