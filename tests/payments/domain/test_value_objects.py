import pytest
from decimal import Decimal
from payments.domain.value_objects import Money, Currency, DomainValidationError


class TestCurrency:
    def test_supported_currencies(self):
        for code in ["RWF", "USD", "EUR", "KES", "GHS", "NGN"]:
            c = Currency(code)
            assert c.code == code

    def test_unsupported_currency_raises(self):
        with pytest.raises(DomainValidationError):
            Currency("XYZ")

    def test_rwf_has_zero_decimals(self):
        c = Currency("RWF")
        assert c.decimals == 0
        assert c.min_minor == 100
        assert c.max_minor == 10_000_000


class TestMoney:
    def test_create_valid_money(self):
        c = Currency("USD")
        m = Money(minor_units=1000, currency=c)  # $10.00
        assert m.minor_units == 1000

    def test_money_below_minimum_raises(self):
        c = Currency("RWF")
        with pytest.raises(DomainValidationError, match="below minimum"):
            Money(minor_units=50, currency=c)

    def test_money_above_maximum_raises(self):
        c = Currency("USD")
        with pytest.raises(DomainValidationError, match="exceeds maximum"):
            Money(minor_units=2_000_000, currency=c)

    def test_from_decimal(self):
        c = Currency("USD")
        m = Money.from_decimal(Decimal("10.99"), c)
        assert m.minor_units == 1099

    def test_addition_same_currency(self):
        c = Currency("USD")
        m1 = Money(1000, c)
        m2 = Money(500, c)
        m3 = m1 + m2
        assert m3.minor_units == 1500

    def test_addition_different_currencies_raises(self):
        c1 = Currency("USD")
        c2 = Currency("EUR")
        m1 = Money(1000, c1)
        m2 = Money(500, c2)
        with pytest.raises(DomainValidationError, match="different currencies"):
            m1 + m2