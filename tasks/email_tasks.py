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
def send_password_reset_email_task(self, user_id: str, token: str, delivery_id: str | None = None) -> bool:
    attempt = int(getattr(self.request, "retries", 0) or 0) + 1
    task_id = getattr(self.request, "id", None)
    try:
        return send_password_reset_email(user_id, token, delivery_id=delivery_id, task_id=task_id, attempt=attempt)
    except Exception as exc:
        if attempt > self.max_retries:
            logger.error(
                "password_reset_email_failed",
                extra={
                    "delivery_id": delivery_id,
                    "task_id": task_id,
                    "user_id": str(user_id),
                    "attempt": attempt,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=True,
            )
            raise

        logger.warning(
            "password_reset_email_retry_scheduled",
            extra={
                "delivery_id": delivery_id,
                "task_id": task_id,
                "user_id": str(user_id),
                "attempt": attempt,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise self.retry(exc=exc)
