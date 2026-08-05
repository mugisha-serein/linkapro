from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class GetBudgetSummaryQuery:
    event_id: uuid.UUID

