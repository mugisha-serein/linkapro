from __future__ import annotations

import logging

from celery import shared_task

from infrastructure.adapters.notifications.resend_email_sender import ResendEmailSender

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
    name="tasks.notifications.send_email_task",
)
def send_email_task(self, *, to: str, template: str, context: dict) -> bool:
    try:
        ResendEmailSender().send(to=to, template=template, context=context)
        return True
    except Exception as exc:
        if int(getattr(self.request, "retries", 0) or 0) >= self.max_retries:
            logger.exception(
                "notification_email_failed",
                extra={"template": template, "to": to, "error_type": exc.__class__.__name__},
            )
            raise

        logger.warning(
            "notification_email_retry_scheduled",
            extra={"template": template, "to": to, "error_type": exc.__class__.__name__},
            exc_info=True,
        )
        raise self.retry(exc=exc)
