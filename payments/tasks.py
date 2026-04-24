from celery import shared_task
from datetime import datetime

from payments.application.commands import ProcessWebhookCommand
from payments.infrastructure.expiry_scanner import DjangoExpiryScanner
from payments.infrastructure.repositories import DjangoPaymentRepository, DjangoWebhookEventRepository
from payments.infrastructure.flutterwave_gateway import FlutterwaveGateway
from payments.infrastructure.audit_logger import DjangoAuditLogger
from payments.infrastructure.retry_scheduler import CeleryRetryScheduler
from payments.application.handlers import PaymentCommandHandlers
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher


@shared_task(bind=True, max_retries=3)
def process_webhook_retry(self, provider_reference: str):
    # This task would be called by the scheduler with a stored webhook payload
    # For simplicity, we fetch the webhook event by provider_reference?
    # The original design stores event_id in Redis or we could pass the event_id directly.
    # For now, we assume the webhook payload is passed along or re-fetched.
    pass


@shared_task
def expire_stale_payments_task():
    now = datetime.utcnow()
    repo = DjangoPaymentRepository()
    scanner = DjangoExpiryScanner()
    handlers = PaymentCommandHandlers(
        payment_repo=repo,
        provider_gateway=FlutterwaveGateway(),
        webhook_repo=DjangoWebhookEventRepository(),
        audit_logger=DjangoAuditLogger(),
        retry_scheduler=CeleryRetryScheduler(),
        expiry_scanner=scanner,
        event_dispatcher=DjangoEventDispatcher(),
    )
    from payments.application.commands import ExpireStalePaymentsCommand
    count = handlers.expire_stale_payments(ExpireStalePaymentsCommand(now=now))
    return f"Expired {count} payments"