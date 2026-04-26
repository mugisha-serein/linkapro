import uuid


from payments.domain.entities import Payment
from payments.domain.enums import PaymentEnv, PaymentMethod
from payments.domain.value_objects import Currency, Money
from payments.domain.velocity import FraudContext, FraudPatternPolicy
from domain.shared.utils import utc_now


class TestFraudPatternPolicy:
    def test_no_fraud(self):
        payment = Payment(
            id=uuid.uuid4(), user_id=uuid.uuid4(), amount=Money(500, Currency("RWF")),
            method=PaymentMethod.CARD, reference="ref", idempotency_key="idem",
            environment=PaymentEnv.TEST
        )
        ctx = FraudContext(duplicate_context_ref=False, account_age_hours=50, step_up_threshold_minor=500_000)
        result = FraudPatternPolicy.apply(payment, ctx, utc_now())
        assert result.flagged is False

    def test_duplicate_context_ref(self):
        payment = Payment(
            id=uuid.uuid4(), user_id=uuid.uuid4(), amount=Money(1000, Currency("RWF")),
            method=PaymentMethod.CARD, reference="ref", idempotency_key="idem",
            environment=PaymentEnv.TEST, context_reference="dup"
        )
        ctx = FraudContext(duplicate_context_ref=True, account_age_hours=50, step_up_threshold_minor=500_000)
        result = FraudPatternPolicy.apply(payment, ctx, utc_now())
        assert result.flagged is True
        assert "DUPLICATE_PURCHASE" in result.patterns

    def test_new_account_high_value(self):
        payment = Payment(
            id=uuid.uuid4(), user_id=uuid.uuid4(), amount=Money(600_000, Currency("RWF")),
            method=PaymentMethod.CARD, reference="ref", idempotency_key="idem",
            environment=PaymentEnv.TEST
        )
        ctx = FraudContext(duplicate_context_ref=False, account_age_hours=10, step_up_threshold_minor=500_000)
        result = FraudPatternPolicy.apply(payment, ctx, utc_now())
        assert result.flagged is True
        assert "NEW_ACCOUNT_HIGH_VALUE" in result.patterns

    def test_threshold_probing(self):
        payment = Payment(
            id=uuid.uuid4(), user_id=uuid.uuid4(), amount=Money(505_000, Currency("RWF")),  # within 1% of 500k
            method=PaymentMethod.CARD, reference="ref", idempotency_key="idem",
            environment=PaymentEnv.TEST
        )
        ctx = FraudContext(duplicate_context_ref=False, account_age_hours=100, step_up_threshold_minor=500_000)
        result = FraudPatternPolicy.apply(payment, ctx, utc_now())
        assert result.flagged is True
        assert "THRESHOLD_PROBING" in result.patterns