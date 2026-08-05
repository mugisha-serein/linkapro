from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class BudgetLineDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    category: str
    description: str
    estimated_cost: float
    actual_cost: Optional[float]
    notes: Optional[str]

