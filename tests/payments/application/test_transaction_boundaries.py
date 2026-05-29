import secrets
import uuid
from itertools import count
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.db import transaction

from django_app.identity.models import User
from django_app.payments.models import Payment as DjangoPayment, WebhookEvent
from payments.application.handlers import PaymentCommandHandlers
from payments.application.ports import VerifiedTransactionDTO
from payments.domain.entities import Payment as DomainPayment
from payments.domain.enums import PaymentEnv, PaymentMethod, PaymentStatus
from payments.domain.value_objects import Currency, Money
from payments.infrastructure.audit_logger import DjangoAuditLogger
from payments.infrastructure.repositories import DjangoPaymentRepository, DjangoWebhookEventRepository
from domain.shared.utils import utc_now


pytestmark = pytest.mark.django_db(transaction=True)


class RecordingEventDispatcher:
    def __init__(self, order):
        self.order = order

    def dispatch_after_commit(self, event) -> None:
        event_name = type(event).__name__

        def _record() -> None:
            self.order.append(f"dispatch:{event_name}")

        transaction.on_commit(_record)


def _build_payment_repo(key_provider, redis_client=None):
    return DjangoPaymentRepository(key_provider=key_provider, redis_client=redis_client)


def _build_key_provider():
    key_provider = Mock()
    wrapped_to_dek = {}
    token_counter = count()

    def wrap_dek(dek):
        wrapped = f"wrapped-dek-{next(token_counter)}".encode("utf-8")
        wrapped_to_dek[wrapped] = dek
        return wrapped

    key_provider.wrap_dek.side_effect = wrap_dek
    key_provider.unwrap_dek.side_effect = lambda wrapped: wrapped_to_dek[wrapped]
    return key_provider


class TestPaymentTransactionBoundaries:
    def test_webhook_success_commits_before_dispatch(self):
        order = []

        key_provider = _build_key_provider()

        redis_client = Mock()
        redis_client.set.return_value = True

        payment_repo = _build_payment_repo(key_provider, redis_client=redis_client)
        webhook_repo = DjangoWebhookEventRepository(key_provider=key_provider)
        audit_logger = DjangoAuditLogger(key_provider=key_provider)
        retry_scheduler = Mock()
        expiry_scanner = Mock()
        event_dispatcher = RecordingEventDispatcher(order)

        user = User.objects.create_user(
            email="success@example.com",
            password="secret",
            first_name="Test",
            last_name="User",
            role="planner",
        )
        payment = DomainPayment(
            id=uuid.uuid4(),
            user_id=user.id,
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="pay_success",
            idempotency_key=str(uuid.uuid4()),
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="flw_test_ref",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=1),
        )
        payment_repo.save(payment)

        real_save_event = webhook_repo.save_event

        def save_event_spy(event_id, status, payload):
            order.append(f"webhook:{status}")
            return real_save_event(event_id, status, payload)

        webhook_repo.save_event = save_event_spy

        audit_log_spy = Mock(side_effect=lambda *args, **kwargs: order.append("audit"))
        audit_logger.log = audit_log_spy

        handler = PaymentCommandHandlers(
            payment_repo=payment_repo,
            provider_gateway=Mock(
                verify_transaction=lambda ref: VerifiedTransactionDTO(
                    provider_reference=ref,
                    status="successful",
                    amount_minor_units=1000,
                    currency_code="RWF",
                    raw_response={},
                )
            ),
            webhook_repo=webhook_repo,
            audit_logger=audit_logger,
            retry_scheduler=retry_scheduler,
            expiry_scanner=expiry_scanner,
            event_dispatcher=event_dispatcher,
        )

        handler.process_webhook(
            Mock(
                event_id="evt_success",
                payload={"data": {"tx_ref": "flw_test_ref"}},
                now=utc_now(),
            )
        )

        assert order == [
            "webhook:PROCESSING",
            "audit",
            "webhook:PROCESSED_SUCCESS",
            "dispatch:PaymentCompleted",
        ]
        assert DjangoPayment.objects.get(reference="pay_success").status == PaymentStatus.SUCCESS.value
        assert WebhookEvent.objects.get(event_id="evt_success").status == "PROCESSED_SUCCESS"
        assert retry_scheduler.schedule_webhook_retry.call_count == 0
        assert redis_client.delete.call_count == 1

    def test_webhook_rollback_reverts_payment_when_audit_fails(self):
        key_provider = _build_key_provider()

        redis_client = Mock()
        redis_client.set.return_value = True

        payment_repo = _build_payment_repo(key_provider, redis_client=redis_client)
        webhook_repo = DjangoWebhookEventRepository(key_provider=key_provider)
        audit_logger = DjangoAuditLogger(key_provider=key_provider)
        retry_scheduler = Mock()
        expiry_scanner = Mock()
        event_dispatcher = Mock()

        user = User.objects.create_user(
            email="rollback@example.com",
            password="secret",
            first_name="Test",
            last_name="User",
            role="planner",
        )
        payment = DomainPayment(
            id=uuid.uuid4(),
            user_id=user.id,
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="pay_rollback",
            idempotency_key=str(uuid.uuid4()),
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="flw_rollback_ref",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=1),
        )
        payment_repo.save(payment)

        webhook_repo.save_event = Mock(wraps=webhook_repo.save_event)
        audit_logger.log = Mock(side_effect=RuntimeError("boom"))

        handler = PaymentCommandHandlers(
            payment_repo=payment_repo,
            provider_gateway=Mock(
                verify_transaction=lambda ref: VerifiedTransactionDTO(
                    provider_reference=ref,
                    status="successful",
                    amount_minor_units=1000,
                    currency_code="RWF",
                    raw_response={},
                )
            ),
            webhook_repo=webhook_repo,
            audit_logger=audit_logger,
            retry_scheduler=retry_scheduler,
            expiry_scanner=expiry_scanner,
            event_dispatcher=event_dispatcher,
        )

        with pytest.raises(RuntimeError):
            handler.process_webhook(
                Mock(
                    event_id="evt_rollback",
                    payload={"data": {"tx_ref": "flw_rollback_ref"}},
                    now=utc_now(),
                )
            )

        assert DjangoPayment.objects.get(reference="pay_rollback").status == PaymentStatus.PENDING.value
        assert not WebhookEvent.objects.filter(event_id="evt_rollback").exists()
        assert event_dispatcher.dispatch_after_commit.call_count == 0
        assert redis_client.delete.call_count == 1

    def test_lock_failure_schedules_retry_after_commit(self):
        key_provider = _build_key_provider()

        redis_client = Mock()
        redis_client.set.return_value = False

        payment_repo = _build_payment_repo(key_provider, redis_client=redis_client)
        webhook_repo = DjangoWebhookEventRepository(key_provider=key_provider)
        audit_logger = DjangoAuditLogger(key_provider=key_provider)
        retry_scheduler = Mock()
        expiry_scanner = Mock()
        event_dispatcher = Mock()

        real_save_event = webhook_repo.save_event
        save_events = []

        def save_event_spy(event_id, status, payload):
            save_events.append(status)
            return real_save_event(event_id, status, payload)

        webhook_repo.save_event = save_event_spy

        handler = PaymentCommandHandlers(
            payment_repo=payment_repo,
            provider_gateway=Mock(),
            webhook_repo=webhook_repo,
            audit_logger=audit_logger,
            retry_scheduler=retry_scheduler,
            expiry_scanner=expiry_scanner,
            event_dispatcher=event_dispatcher,
        )

        handler.process_webhook(
            Mock(
                event_id="evt_retry",
                payload={"data": {"tx_ref": "flw_missing_lock"}},
                now=utc_now(),
            )
        )

        assert save_events == ["LOCK_FAILED_RETRY"]
        assert retry_scheduler.schedule_webhook_retry.call_count == 1
        assert retry_scheduler.schedule_webhook_retry.call_args.args == ("flw_missing_lock", 30)
        assert redis_client.delete.call_count == 0
