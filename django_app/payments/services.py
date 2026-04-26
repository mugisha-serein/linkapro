from payments.infrastructure.repositories import (
    DjangoPaymentRepository,
    DjangoWebhookEventRepository,
)
from payments.infrastructure.flutterwave_gateway import FlutterwaveGateway
from payments.infrastructure.audit_logger import DjangoAuditLogger
from payments.infrastructure.retry_scheduler import CeleryRetryScheduler
from payments.infrastructure.expiry_scanner import DjangoExpiryScanner
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher
from payments.application.handlers import PaymentCommandHandlers
from payments.application.query_handlers import PaymentQueryHandlers
from payments.infrastructure.vault_key_provider import VaultKeyProvider


def get_command_handlers() -> PaymentCommandHandlers:
    key_provider = VaultKeyProvider()
    return PaymentCommandHandlers(
        payment_repo=DjangoPaymentRepository(key_provider),
        provider_gateway=FlutterwaveGateway(),
        webhook_repo=DjangoWebhookEventRepository(key_provider),
        audit_logger=DjangoAuditLogger(key_provider),
        retry_scheduler=CeleryRetryScheduler(),
        expiry_scanner=DjangoExpiryScanner(),
        event_dispatcher=DjangoEventDispatcher(),
    )


def get_query_handlers() -> PaymentQueryHandlers:
    return PaymentQueryHandlers(
        payment_repo=DjangoPaymentRepository(),
    )