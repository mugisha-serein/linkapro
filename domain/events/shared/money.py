from dataclasses import dataclass
from decimal import Decimal
from typing import Union

MoneyInput = Union["Money", Decimal, int, str]


@dataclass(frozen=True)
class Money:
    """Decimal-backed money value used by event budget concepts."""

    amount: Decimal

    def __init__(self, amount: MoneyInput):
        object.__setattr__(self, "amount", self._coerce_amount(amount))

    def __add__(self, other: MoneyInput) -> "Money":
        return Money(self.amount + self._coerce_amount(other))

    def __sub__(self, other: MoneyInput) -> "Money":
        return Money(self.amount - self._coerce_amount(other))

    def __lt__(self, other: MoneyInput) -> bool:
        return self.amount < self._coerce_amount(other)

    def __le__(self, other: MoneyInput) -> bool:
        return self.amount <= self._coerce_amount(other)

    def __gt__(self, other: MoneyInput) -> bool:
        return self.amount > self._coerce_amount(other)

    def __ge__(self, other: MoneyInput) -> bool:
        return self.amount >= self._coerce_amount(other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (Money, Decimal, int, str)):
            return NotImplemented
        return self.amount == self._coerce_amount(other)

    @staticmethod
    def _coerce_amount(amount: MoneyInput) -> Decimal:
        if isinstance(amount, Money):
            return amount.amount
        if isinstance(amount, Decimal):
            return amount
        if isinstance(amount, int):
            return Decimal(amount)
        if isinstance(amount, str):
            return Decimal(amount)
        raise TypeError("Money amount must be Money, Decimal, int, or str")
