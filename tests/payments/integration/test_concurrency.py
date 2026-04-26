import threading
import uuid
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from payments.application.commands import ProcessWebhookCommand
from payments.application.handlers import PaymentCommandHandlers
from payments.domain.entities import Payment
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentMethod, PaymentEnv, PaymentStatus
from domain.shared.utils import utc_now


def create_webhook_cmd():
    return ProcessWebhookCommand(
        event_id=str(uuid.uuid4()),
        event_type="charge.completed",
        payload={"data": {"tx_ref": "flw_test_ref"}},
        headers={},
        now=utc_now(),
    )


def create_test_payment():
    return Payment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        amount=Money(1000, Currency("RWF")),
        method=PaymentMethod.CARD,
        reference="pay_test",
        idempotency_key="idem",
        environment=PaymentEnv.TEST,
        status=PaymentStatus.PENDING,
        provider_reference="flw_test_ref",
        created_at=utc_now(),
    )


@pytest.mark.django_db(transaction=True)
class TestConcurrency:
    def test_simultaneous_webhooks_with_lock(self, mock_ports):
        payment = create_test_payment()
        mock_ports["webhook_repo"].exists.return_value = False
        mock_ports["payment_repo"].find_by_provider_reference.return_value = payment
        mock_ports["provider_gateway"].verify_transaction.return_value = Mock(
            status="successful",
            provider_reference="flw_test_ref",
            amount_minor_units=1000,
            currency_code="RWF",
        )

        handlers = PaymentCommandHandlers(**mock_ports)

        def first_webhook():
            mock_ports["payment_repo"].acquire_lock.return_value = True
            handlers.process_webhook(create_webhook_cmd())

        def second_webhook():
            mock_ports["payment_repo"].acquire_lock.return_value = False
            handlers.process_webhook(create_webhook_cmd())

        t1 = threading.Thread(target=first_webhook)
        t2 = threading.Thread(target=second_webhook)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Second webhook should have scheduled a retry
        mock_ports["retry_scheduler"].schedule_webhook_retry.assert_called_once()