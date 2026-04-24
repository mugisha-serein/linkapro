import uuid
from datetime import timedelta
import pytest
from payments.domain.entities import Payment
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentStatus, PaymentMethod, PaymentEnv
from payments.domain.policy import PaymentPolicy
from domain.shared.utils import utc_now


class TestPaymentPolicy:
    def test_initiate_allowed(self):
        payment = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="ref",
            idempotency_key="idem",
            environment=PaymentEnv.TEST,
        )
        now = utc_now()
        result = PaymentPolicy.apply(payment, "INITIATE", None, now)
        assert result.allowed is True
        assert result.next_state == PaymentStatus.PENDING

    def test_confirm_success_fraud_on_amount_mismatch(self):
        payment = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="ref",
            idempotency_key="idem",
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            provider_reference="prov123",
        )
        now = utc_now()
        context = type('Context', (), {
            'provider_verified': True,
            'provider_reference': 'prov123',
            'provider_amount_minor': 2000,  # mismatch
            'provider_currency': 'RWF',
            'environment': PaymentEnv.TEST,
        })
        result = PaymentPolicy.apply(payment, "CONFIRM_SUCCESS", context, now)
        assert result.allowed is False
        assert result.fraud_signal is True
        assert "Amount mismatch" in result.reason

    def test_expire_allowed_when_expired(self):
        now = utc_now()
        payment = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="ref",
            idempotency_key="idem",
            environment=PaymentEnv.TEST,
            status=PaymentStatus.PENDING,
            created_at=now - timedelta(hours=1),
            expires_at=now - timedelta(minutes=10),
        )
        result = PaymentPolicy.apply(payment, "EXPIRE", None, now)
        assert result.allowed is True
        assert result.next_state == PaymentStatus.EXPIRED