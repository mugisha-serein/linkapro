import uuid
from unittest.mock import Mock, ANY
import pytest
from payments.application.commands import InitiatePaymentCommand, ProcessWebhookCommand
from payments.application.handlers import PaymentCommandHandlers
from payments.application.exceptions import PaymentNotAllowedError
from payments.domain.entities import Payment
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentMethod, PaymentEnv, PaymentStatus
from domain.shared.utils import utc_now


@pytest.fixture
def mock_ports():
    return {
        "payment_repo": Mock(),
        "provider_gateway": Mock(),
        "webhook_repo": Mock(),
        "audit_logger": Mock(),
        "retry_scheduler": Mock(),
        "expiry_scanner": Mock(),
        "event_dispatcher": Mock(),
    }


@pytest.fixture
def handlers(mock_ports):
    return PaymentCommandHandlers(**mock_ports)


class TestInitiatePayment:
    def test_new_payment_success(self, handlers, mock_ports):
        mock_ports["payment_repo"].find_by_idempotency_key.return_value = None
        mock_ports["provider_gateway"].create_payment_link.return_value = ("https://pay.link", "flw_tx_ref")
        mock_ports["payment_repo"].save.side_effect = lambda p: p

        cmd = InitiatePaymentCommand(
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            idempotency_key="idem",
            redirect_base_url="http://example.com",
            customer_email="user@example.com",
            environment=PaymentEnv.TEST,
        )
        result = handlers.initiate_payment(cmd)
        assert result.reference.startswith("pay_")
        mock_ports["audit_logger"].log.assert_called_once()

    def test_idempotency_returns_existing(self, handlers, mock_ports):
        existing = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="pay_existing",
            idempotency_key="idem",
            environment=PaymentEnv.TEST,
        )
        mock_ports["payment_repo"].find_by_idempotency_key.return_value = existing

        cmd = InitiatePaymentCommand(
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            idempotency_key="idem",
            redirect_base_url="http://example.com",
            customer_email="user@example.com",
            environment=PaymentEnv.TEST,
        )
        result = handlers.initiate_payment(cmd)
        assert result.reference == "pay_existing"
        mock_ports["provider_gateway"].create_payment_link.assert_not_called()


class TestProcessWebhook:
    def test_webhook_idempotency_skips_processing(self, handlers, mock_ports):
        mock_ports["webhook_repo"].exists.return_value = True
        cmd = ProcessWebhookCommand(
            event_id="evt123",
            event_type="charge.completed",
            payload={},
            headers={},
            now=utc_now(),
        )
        handlers.process_webhook(cmd)
        mock_ports["webhook_repo"].save_event.assert_not_called()

    def test_webhook_fraud_signal_does_not_transition(self, handlers, mock_ports):
        mock_ports["webhook_repo"].exists.return_value = False
        payment = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="ref",
            idempotency_key="idem",
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="flw_tx",
        )
        mock_ports["payment_repo"].find_by_provider_reference.return_value = payment
        mock_ports["payment_repo"].acquire_lock.return_value = True
        mock_ports["provider_gateway"].verify_transaction.return_value = Mock(
            status="successful",
            provider_reference="flw_tx",
            amount_minor_units=2000,  # mismatch
            currency_code="RWF",
        )
        cmd = ProcessWebhookCommand(
            event_id="evt123",
            event_type="charge.completed",
            payload={"data": {"tx_ref": "flw_tx"}},
            headers={},
            now=utc_now(),
        )
        handlers.process_webhook(cmd)
        # Payment should NOT be saved with SUCCESS
        assert payment.status == PaymentStatus.PENDING
        mock_ports["event_dispatcher"].dispatch.assert_called()  # FraudSignalEvent