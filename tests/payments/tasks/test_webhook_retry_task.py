import uuid
from unittest.mock import Mock, patch

import pytest
from datetime import timedelta
from django.utils import timezone

from django_app.identity.models import User
from django_app.payments.models import WebhookEvent
from payments.domain.enums import PaymentEnv, PaymentMethod, PaymentStatus
from payments.domain.entities import Payment as DomainPayment
from payments.domain.value_objects import Currency, Money
from payments.infrastructure.repositories import DjangoPaymentRepository, DjangoWebhookEventRepository
from payments.infrastructure.retry_scheduler import CeleryRetryScheduler
from payments.tasks import process_webhook_retry
from domain.shared.utils import utc_now


pytestmark = pytest.mark.django_db(transaction=True)


def _build_key_provider():
    key_provider = Mock()
    wrapped_to_dek = {}
    counter = 0

    def wrap_dek(dek):
        nonlocal counter
        wrapped = f"wrapped-dek-{counter}".encode("utf-8")
        counter += 1
        wrapped_to_dek[wrapped] = dek
        return wrapped

    key_provider.wrap_dek.side_effect = wrap_dek
    key_provider.unwrap_dek.side_effect = lambda wrapped: wrapped_to_dek[wrapped]
    return key_provider


class TestWebhookRetryTask:
    def test_retry_replays_persisted_webhook_and_resets_counter(self):
        key_provider = _build_key_provider()
        payment_repo = DjangoPaymentRepository(key_provider=key_provider, redis_client=Mock())
        webhook_repo = DjangoWebhookEventRepository(key_provider=key_provider)

        user = User.objects.create_user(
            email="retry@example.com",
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
            reference="pay_retry",
            idempotency_key=str(uuid.uuid4()),
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="flw_retry_ref",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=1),
        )
        payment_repo.save(payment)

        webhook_repo.save_event(
            "evt_retry",
            WebhookEvent.Status.LOCK_FAILED_RETRY,
            {"event": "charge.completed", "data": {"tx_ref": "flw_retry_ref"}},
        )

        handler = Mock()

        def replay_webhook(cmd, allow_existing_event):
            assert allow_existing_event is True
            assert cmd.event_id == "evt_retry"
            assert cmd.payload["data"]["tx_ref"] == "flw_retry_ref"
            WebhookEvent.objects.filter(event_id="evt_retry").update(
                status=WebhookEvent.Status.PROCESSED_SUCCESS,
                processed_at=timezone.now(),
            )

        handler._process_webhook.side_effect = replay_webhook
        scheduler = Mock()

        with patch("payments.tasks.build_payment_key_provider", return_value=key_provider), \
             patch("payments.tasks.build_payment_command_handlers", return_value=handler), \
             patch("payments.tasks.CeleryRetryScheduler", return_value=scheduler):
            result = process_webhook_retry.apply(args=["flw_retry_ref"]).get()

        assert result["status"] == "completed"
        assert result["final_status"] == WebhookEvent.Status.PROCESSED_SUCCESS
        assert handler._process_webhook.call_count == 1
        assert scheduler.reset_webhook_retry.call_args.args == ("flw_retry_ref",)

    def test_retry_skips_terminal_event(self):
        key_provider = _build_key_provider()
        webhook_repo = DjangoWebhookEventRepository(key_provider=key_provider)

        webhook_repo.save_event(
            "evt_terminal",
            WebhookEvent.Status.PROCESSED_SUCCESS,
            {"event": "charge.completed", "data": {"tx_ref": "flw_terminal_ref"}},
        )

        handler = Mock()
        scheduler = Mock()

        with patch("payments.tasks.build_payment_key_provider", return_value=key_provider), \
             patch("payments.tasks.build_payment_command_handlers", return_value=handler), \
             patch("payments.tasks.CeleryRetryScheduler", return_value=scheduler):
            result = process_webhook_retry.apply(args=["flw_terminal_ref"]).get()

        assert result["status"] == "terminal"
        assert handler._process_webhook.call_count == 0
        assert scheduler.reset_webhook_retry.call_args.args == ("flw_terminal_ref",)

    def test_scheduler_bounded_retry_count(self):
        redis_client = Mock()
        redis_client.incr.side_effect = [1, 2, 3, 4]

        scheduler = CeleryRetryScheduler(redis_client=redis_client, max_attempts=3)

        with patch("payments.infrastructure.retry_scheduler.current_app.send_task") as send_task:
            for _ in range(4):
                scheduler.schedule_webhook_retry("flw_bound_ref", 30)

        assert send_task.call_count == 3
        assert send_task.call_args.args[0] == "payments.tasks.process_webhook_retry"

    def test_task_is_registered_with_celery_app(self):
        from tasks.celery import app as celery_app

        assert "payments.tasks.process_webhook_retry" in celery_app.tasks
