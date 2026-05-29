import uuid
import secrets
import pytest
from django.urls import reverse
from unittest.mock import MagicMock, patch
from datetime import timedelta

from django_app.identity.models import User
from django_app.payments.models import Payment as DjangoPayment, WebhookEvent
from payments.infrastructure.repositories import DjangoPaymentRepository
from payments.application.handlers import PaymentCommandHandlers
from payments.domain.entities import Payment as DomainPayment
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentMethod, PaymentEnv, PaymentStatus
from domain.shared.utils import utc_now

pytestmark = pytest.mark.django_db(transaction=True)


class TestWebhookE2E:
    @patch("django_app.payments.views.get_command_handlers")
    def test_full_webhook_success_flow(
        self,
        mock_get_handlers,
        client,
        settings,
    ):
        # --- Mock key provider and Redis ---
        mock_key_provider = MagicMock()
        last_dek = {}

        def wrap_dek(dek):
            last_dek["value"] = dek
            return b"fake_wrapped_dek"

        mock_key_provider.wrap_dek.side_effect = wrap_dek
        mock_key_provider.unwrap_dek.side_effect = lambda encrypted: last_dek["value"]

        mock_redis = MagicMock()
        mock_redis.set.return_value = True   # lock acquisition succeeds

        # --- Create real repository with mocked infrastructure ---
        repo = DjangoPaymentRepository(
            key_provider=mock_key_provider,
            redis_client=mock_redis,
        )

        # --- Mock other dependencies ---
        mock_webhook_repo = MagicMock()
        mock_webhook_repo.exists.return_value = False   # ‼️ Critical fix: not already processed
        mock_webhook_repo.save_event = MagicMock()

        mock_audit_logger = MagicMock()
        mock_retry_scheduler = MagicMock()
        mock_expiry_scanner = MagicMock()
        mock_event_dispatcher = MagicMock()

        # --- Build handler ---
        handler = PaymentCommandHandlers(
            payment_repo=repo,
            provider_gateway=MagicMock(),
            webhook_repo=mock_webhook_repo,
            audit_logger=mock_audit_logger,
            retry_scheduler=mock_retry_scheduler,
            expiry_scanner=mock_expiry_scanner,
            event_dispatcher=mock_event_dispatcher,
        )

        # --- Inject successful verification ---
        def verify_success(ref):
            class DTO:
                status = "successful"
                provider_reference = "flw_test_ref"
                amount_minor_units = 1000
                currency_code = "RWF"
                raw_response = {"status": "success", "data": {}}
            return DTO()
        handler.provider_gateway.verify_transaction = verify_success

        mock_get_handlers.return_value = handler

        # --- Create user and payment ---
        user = User.objects.create_user(
            email="u@t.com",
            password="p",
            first_name="Test",
            last_name="User",
            role="planner"
        )
        domain_payment = DomainPayment(
            id=uuid.uuid4(),
            user_id=user.id,
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="pay_test",
            idempotency_key=str(uuid.uuid4()),
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="flw_test_ref",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=1),
        )
        repo.save(domain_payment)

        # Clear existing webhook events
        WebhookEvent.objects.filter(event_id="evt_webhook").delete()

        settings.FLW_SECRET_HASH = "secret"
        url = reverse("payments:webhook")

        response = client.post(
            url,
            data={
                "id": "evt_webhook",
                "event": "charge.completed",
                "data": {"tx_ref": "flw_test_ref"}
            },
            content_type="application/json",
            HTTP_VERIF_HASH="secret",
        )

        assert response.status_code == 200

        payment = DjangoPayment.objects.get(reference="pay_test")
        assert payment.status == "success"
