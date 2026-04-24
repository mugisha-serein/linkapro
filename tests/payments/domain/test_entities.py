import uuid
from datetime import timedelta
import pytest
from payments.domain.entities import Payment, InvalidTransitionError
from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentStatus, PaymentMethod, PaymentEnv
from domain.shared.utils import utc_now


class TestPayment:
    def test_payment_creation_defaults(self):
        now = utc_now()
        payment = Payment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD,
            reference="ref123",
            idempotency_key="idem456",
            environment=PaymentEnv.TEST,
            created_at=now,
        )
        assert payment.status == PaymentStatus.INITIATED
        assert payment.expires_at == now + timedelta(minutes=30)

    def test_valid_transitions(self):
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
        payment.transition_to(PaymentStatus.PENDING, now)
        assert payment.status == PaymentStatus.PENDING

        payment.transition_to(PaymentStatus.SUCCESS, now)
        assert payment.status == PaymentStatus.SUCCESS

    def test_invalid_transition_raises(self):
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
        with pytest.raises(InvalidTransitionError):
            payment.transition_to(PaymentStatus.SUCCESS, now)  # from INITIATED not allowed

    def test_metadata_validation(self):
        with pytest.raises(ValueError, match="metadata cannot exceed 10 keys"):
            Payment(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                amount=Money(1000, Currency("RWF")),
                method=PaymentMethod.CARD,
                reference="ref",
                idempotency_key="idem",
                environment=PaymentEnv.TEST,
                metadata={f"k{i}": i for i in range(11)},
            )