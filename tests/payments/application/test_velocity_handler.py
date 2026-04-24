from unittest.mock import MagicMock
import pytest
from datetime import datetime, timedelta
import uuid
from payments.application.handlers import PaymentCommandHandlers
from payments.application.commands import InitiatePaymentCommand
from payments.application.exceptions import VelocityLimitExceededError, FraudFlaggedError
from payments.domain.velocity import VelocityContext, FraudContext
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentMethod, PaymentEnv

@pytest.fixture
def mock_ports():
    return {
        "payment_repo": MagicMock(),
        "provider_gateway": MagicMock(),
        "webhook_repo": MagicMock(),
        "audit_logger": MagicMock(),
        "retry_scheduler": MagicMock(),
        "expiry_scanner": MagicMock(),
        "event_dispatcher": MagicMock(),
    }

@pytest.fixture
def handler(mock_ports):
    return PaymentCommandHandlers(**mock_ports)

def test_velocity_blocks_if_limit_exceeded(handler, mock_ports):
    # Simulate idempotency key not found
    mock_ports["payment_repo"].find_by_idempotency_key.return_value = None
    # Velocity context that exceeds hourly limit
    mock_ports["payment_repo"].get_velocity_context.return_value = VelocityContext(
        payments_last_hour=5, payments_last_day=0, amount_last_day_minor=0,
        failed_last_hour=0, unique_vendors_last_hour=0, account_age_hours=10
    )

    cmd = InitiatePaymentCommand(
        user_id=uuid.uuid4(), amount=Money(1000, Currency("RWF")), method=PaymentMethod.CARD,
        idempotency_key="idem", redirect_base_url="http://x", customer_email="a@b.com",
        environment=PaymentEnv.TEST
    )
    with pytest.raises(VelocityLimitExceededError):
        handler.initiate_payment(cmd)

def test_fraud_flag_raises_review(handler, mock_ports):
    mock_ports["payment_repo"].find_by_idempotency_key.return_value = None
    mock_ports["payment_repo"].get_velocity_context.return_value = VelocityContext(
        payments_last_hour=0, payments_last_day=0, amount_last_day_minor=0,
        failed_last_hour=0, unique_vendors_last_hour=0, account_age_hours=10
    )
    mock_ports["payment_repo"].find_duplicate_context_ref.return_value = True  # duplicate

    cmd = InitiatePaymentCommand(
        user_id=uuid.uuid4(), amount=Money(1000, Currency("RWF")), method=PaymentMethod.CARD,
        idempotency_key="idem", redirect_base_url="http://x", customer_email="a@b.com",
        context_reference="dup_ref", environment=PaymentEnv.TEST
    )
    with pytest.raises(FraudFlaggedError):
        handler.initiate_payment(cmd)