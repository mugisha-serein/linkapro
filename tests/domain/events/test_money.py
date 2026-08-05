from decimal import Decimal

import pytest

from domain.events.shared.money import Money


def test_money_adds_and_subtracts_decimal_backed_amounts():
    amount = Money("12.50")

    assert amount + Money("7.25") == Money("19.75")
    assert amount - Decimal("2.50") == Money("10.00")


def test_money_compares_amounts():
    amount = Money("12.50")

    assert amount > Money("10.00")
    assert amount >= Decimal("12.50")
    assert amount < "13.00"
    assert amount <= 13


def test_money_rejects_float_input():
    with pytest.raises(TypeError, match="Money amount must be Money, Decimal, int, or str"):
        Money(1.25)
