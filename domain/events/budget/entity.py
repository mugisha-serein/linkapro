import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Union

from domain.events.budget.errors import NegativeBudgetAmount
from domain.events.budget.value_objects import BudgetCategory
from domain.events.shared.money import Money
from domain.shared.utils import utc_now

BudgetAmountInput = Union[Money, Decimal, int, str, float]


@dataclass
class BudgetLine:
    """Individual budget entry."""

    id: uuid.UUID
    event_id: uuid.UUID
    category: BudgetCategory
    description: str
    estimated_cost: Money
    actual_cost: Optional[Money] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.estimated_cost = self._coerce_money(self.estimated_cost)
        if self.actual_cost is not None:
            self.actual_cost = self._coerce_money(self.actual_cost)
        self._validate_amount(self.estimated_cost, "Estimated cost")
        if self.actual_cost is not None:
            self._validate_amount(self.actual_cost, "Actual cost")

    def update_estimate(self, estimated_cost: BudgetAmountInput) -> None:
        amount = self._coerce_money(estimated_cost)
        self._validate_amount(amount, "Estimated cost")
        self.estimated_cost = amount
        self.updated_at = utc_now()

    def set_actual_cost(self, amount: BudgetAmountInput) -> None:
        amount = self._coerce_money(amount)
        self._validate_amount(amount, "Actual cost")
        self.actual_cost = amount
        self.updated_at = utc_now()

    @staticmethod
    def _coerce_money(amount: BudgetAmountInput) -> Money:
        if isinstance(amount, float):
            return Money(str(amount))
        return Money(amount)

    @staticmethod
    def _validate_amount(amount: Money, label: str) -> None:
        if amount < Money(0):
            raise NegativeBudgetAmount(f"{label} must be greater than or equal to 0")
