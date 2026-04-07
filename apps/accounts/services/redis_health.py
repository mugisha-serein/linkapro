import redis
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('accounts.redis')


class RedisHealthMonitor:
    """
    Monitors Redis connection health and logs connection state changes.
    Provides health check status for monitoring/alerting systems.
    """

    def __init__(self):
        self.redis_client = None
        self.last_status = None
        self.last_check = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Redis connection for health checks."""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        except Exception as exc:
            logger.error(f'Failed to initialize Redis monitoring client: {exc}')
            self.redis_client = None

    def check_health(self):
        """
        Perform a health check on Redis connection.
        
        Returns:
            dict: {
                'healthy': bool,
                'timestamp': str (ISO format),
                'response_time_ms': float,
                'error': str or None,
                'keys_count': int or None
            }
        """
        start = timezone.now()
        error = None
        response_time_ms = None
        keys_count = None
        healthy = False

        if not self.redis_client:
            error = 'Redis client not initialized'
            logger.warning(f'Health check failed: {error}')
            self._log_status_change('unhealthy', error)
            return {
                'healthy': False,
                'timestamp': timezone.now().isoformat(),
                'response_time_ms': None,
                'error': error,
                'keys_count': None
            }

        try:
            # PING test
            self.redis_client.ping()
            response_time_ms = (timezone.now() - start).total_seconds() * 1000

            # Get approximate key count
            info = self.redis_client.info('stats')
            keys_count = info.get('total_commands_processed', 0)

            healthy = True
            self._log_status_change('healthy', None)
            logger.info(
                'Redis health check passed',
                extra={'response_time_ms': response_time_ms, 'keys_count': keys_count}
            )

        except redis.ConnectionError as exc:
            error = f'Connection error: {str(exc)}'
            response_time_ms = (timezone.now() - start).total_seconds() * 1000
            logger.error(
                f'Redis health check failed: {error}',
                extra={'response_time_ms': response_time_ms}
            )
            self._log_status_change('unhealthy', error)

        except Exception as exc:
            error = f'Unexpected error: {str(exc)}'
            response_time_ms = (timezone.now() - start).total_seconds() * 1000
            logger.error(
                f'Redis health check error: {error}',
                extra={'response_time_ms': response_time_ms}
            )
            self._log_status_change('unhealthy', error)

        self.last_check = timezone.now()

        return {
            'healthy': healthy,
            'timestamp': timezone.now().isoformat(),
            'response_time_ms': response_time_ms,
            'error': error,
            'keys_count': keys_count
        }

    def _log_status_change(self, new_status, error=None):
        """Log state transitions for monitoring/alerting."""
        if self.last_status != new_status:
            if new_status == 'healthy':
                logger.info('Redis connection restored')
            elif new_status == 'unhealthy':
                logger.error(f'Redis connection lost: {error}')
            self.last_status = new_status

    def is_healthy(self):
        """Quick health status without detailed info."""
        health = self.check_health()
        return health['healthy']


# Global instance
redis_health_monitor = RedisHealthMonitor()
