"""Centralized construction for payment infrastructure and handlers."""
from typing import Optional

from payments.application.ports import IKeyProvider
from payments.application.handlers import PaymentCommandHandlers
from payments.application.query_handlers import PaymentQueryHandlers
from payments.infrastructure.audit_logger import DjangoAuditLogger
from payments.infrastructure.expiry_scanner import DjangoExpiryScanner
from payments.infrastructure.flutterwave_gateway import FlutterwaveGateway
from payments.infrastructure.repositories import (
    DjangoPaymentRepository,
    DjangoWebhookEventRepository,
)
from payments.infrastructure.retry_scheduler import CeleryRetryScheduler
from payments.infrastructure.vault_key_provider import VaultKeyProvider
from payments.infrastructure.django_event_outbox import DjangoPaymentEventOutboxDispatcher


def build_payment_key_provider() -> VaultKeyProvider:
    return VaultKeyProvider()


def build_payment_expiry_scanner(key_provider: Optional[IKeyProvider] = None) -> DjangoExpiryScanner:
    if key_provider is None:
        key_provider = build_payment_key_provider()
    return DjangoExpiryScanner(key_provider)


def build_payment_command_handlers() -> PaymentCommandHandlers:
    key_provider = build_payment_key_provider()
    return PaymentCommandHandlers(
        payment_repo=DjangoPaymentRepository(key_provider),
        provider_gateway=FlutterwaveGateway(),
        webhook_repo=DjangoWebhookEventRepository(key_provider),
        audit_logger=DjangoAuditLogger(key_provider),
        retry_scheduler=CeleryRetryScheduler(),
        expiry_scanner=build_payment_expiry_scanner(key_provider),
        event_dispatcher=DjangoPaymentEventOutboxDispatcher(),
    )


def build_payment_query_handlers() -> PaymentQueryHandlers:
    key_provider = build_payment_key_provider()
    return PaymentQueryHandlers(
        payment_repo=DjangoPaymentRepository(key_provider),
    )
