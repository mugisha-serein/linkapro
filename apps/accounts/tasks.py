"""
Celery tasks for accounts app security monitoring.
"""

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger('accounts.tasks')


@shared_task(bind=True, max_retries=3)
def check_redis_health(self):
    """
    Periodic task to check Redis connection health.
    Runs every 5 minutes.
    """
    try:
        from .services.redis_health import redis_health_monitor
        
        health = redis_health_monitor.check_health()
        
        if not health['healthy']:
            logger.error(
                'Redis health check failed',
                extra={
                    'error': health['error'],
                    'response_time_ms': health['response_time_ms']
                }
            )
            # Could send alert/notification here
        else:
            logger.debug(
                'Redis health check passed',
                extra={'response_time_ms': health['response_time_ms']}
            )
        
        return health
    except Exception as exc:
        logger.error(f'Redis health check task failed: {exc}')
        # Retry with exponential backoff
        self.retry(countdown=60 * (2 ** self.request.retries))


@shared_task
def send_anomaly_notification(user_id, anomaly_type, anomaly_data):
    """
    Send notification to user about detected anomalies.
    
    Args:
        user_id: UUID of user
        anomaly_type: Type of anomaly detected (e.g., 'new_location')
        anomaly_data: Dict with anomaly details
    """
    try:
        from django.contrib.auth import get_user_model
        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        User = get_user_model()
        user = User.objects.get(id=user_id)

        if anomaly_type == 'new_location':
            country = anomaly_data.get('country_code', 'Unknown')
            ip_address = anomaly_data.get('ip_address', 'Unknown')

            # Send email notification
            subject = 'New login location detected'
            context = {
                'user_name': user.email,
                'country': country,
                'ip_address': ip_address,
                'timestamp': timezone.now().isoformat()
            }
            html_message = render_to_string('accounts/anomaly_notification.html', context)
            
            send_mail(
                subject,
                f'New login detected from {country}',
                'security@linkapro.rw',
                [user.email],
                html_message=html_message,
                fail_silently=True
            )

            logger.info(
                'Anomaly notification sent',
                extra={'user_id': str(user_id), 'type': anomaly_type}
            )

    except Exception as exc:
        logger.error(f'Failed to send anomaly notification: {exc}')


@shared_task
def cleanup_old_login_activities():
    """
    Clean up old login activity logs (keep last 90 days).
    Runs daily.
    """
    try:
        from datetime import timedelta
        from .models import LoginActivityLog

        cutoff_date = timezone.now() - timedelta(days=90)
        deleted_count, _ = LoginActivityLog.objects.filter(timestamp__lt=cutoff_date).delete()
        
        logger.info(f'Cleaned up {deleted_count} old login activity logs')
        return deleted_count

    except Exception as exc:
        logger.error(f'Failed to cleanup login activities: {exc}')
