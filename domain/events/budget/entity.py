import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.events.budget.value_objects import BudgetCategory
from domain.shared.utils import utc_now


@dataclass
class BudgetLine:
    """Individual budget entry."""

    id: uuid.UUID
    event_id: uuid.UUID
    category: BudgetCategory
    description: str
    estimated_cost: float
    actual_cost: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def set_actual_cost(self, amount: float) -> None:
        self.actual_cost = amount
        self.updated_at = utc_now()

