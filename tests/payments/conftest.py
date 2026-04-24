import pytest
from unittest.mock import Mock


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
def create_test_payment():
    from payments.domain.entities import Payment
    from payments.domain.value_objects import Money, Currency
    from payments.domain.enums import PaymentMethod, PaymentEnv, PaymentStatus
    import uuid
    from datetime import datetime

    def _create(**kwargs):
        defaults = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "amount": Money(1000, Currency("RWF")),
            "method": PaymentMethod.CARD,
            "reference": "pay_test",
            "idempotency_key": "idem",
            "environment": PaymentEnv.TEST,
            "status": PaymentStatus.PENDING,
            "provider_reference": "flw_test_ref",
            "created_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return Payment(**defaults)
    return _create