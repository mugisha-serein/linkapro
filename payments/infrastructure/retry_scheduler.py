from celery import current_app
from payments.application.ports import IRetryScheduler


class CeleryRetryScheduler(IRetryScheduler):
    def schedule_webhook_retry(self, provider_reference: str, delay_seconds: int) -> None:
        current_app.send_task(
            "evplan.payments.tasks.process_webhook_retry",
            args=[provider_reference],
            countdown=delay_seconds,
        )