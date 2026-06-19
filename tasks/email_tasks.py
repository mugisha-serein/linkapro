import logging

from celery import shared_task

from django_app.identity.password_reset_email import send_password_reset_email

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
    name="tasks.email_tasks.send_password_reset_email_task",
)
def send_password_reset_email_task(self, user_id: str, token: str) -> bool:
    try:
        return send_password_reset_email(user_id, token)
    except Exception as exc:
        logger.warning(
            "forgot_password_email_task_retry",
            extra={"user_id": str(user_id), "error_type": exc.__class__.__name__},
            exc_info=True,
        )
        raise self.retry(exc=exc)
