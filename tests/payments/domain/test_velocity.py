import pytest
from payments.domain.velocity import (
    VelocityPolicy, VelocityResult, VelocityContext,
    FraudPatternPolicy, FraudResult, FraudContext,
)
from payments.domain.value_objects import Money, Currency
from payments.domain.entities import Payment
from payments.domain.enums import PaymentMethod, PaymentEnv
from domain.shared.utils import utc_now

def make_context(**kwargs):
    defaults = {
        "payments_last_hour": 0,
        "payments_last_day": 0,
        "amount_last_day_minor": 0,
        "failed_last_hour": 0,
        "unique_vendors_last_hour": 0,
        "account_age_hours": 100,
    }
    defaults.update(kwargs)
    return VelocityContext(**defaults)


class TestVelocityPolicy:
    def test_allowed_when_empty(self):
        ctx = make_context()
        result = VelocityPolicy.apply("user1", ctx, utc_now())
        assert result.allowed is True

    def test_block_hourly_limit(self):
        ctx = make_context(payments_last_hour=5)
        result = VelocityPolicy.apply("u", ctx, utc_now())
        assert result.allowed is False
        assert "Hourly" in result.reason

    def test_block_daily_limit(self):
        ctx = make_context(payments_last_day=20)
        result = VelocityPolicy.apply("u", ctx, utc_now())
        assert result.allowed is False
        assert "Daily payment limit" in result.reason

    def test_block_amount_limit(self):
        ctx = make_context(amount_last_day_minor=2_000_000)
        result = VelocityPolicy.apply("u", ctx, utc_now())
        assert result.allowed is False
        assert "amount" in result.reason.lower()

    def test_flag_unique_vendors(self):
        ctx = make_context(unique_vendors_last_hour=3)
        result = VelocityPolicy.apply("u", ctx, utc_now())
        assert result.allowed is True
        assert result.flag is True