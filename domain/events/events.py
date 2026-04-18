"""Domain events for event planning context."""
from dataclasses import dataclass
import uuid
from datetime import datetime


@dataclass(frozen=True)
class EventCreated:
    event_id: uuid.UUID
    planner_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True)
class ChecklistCreated:
    checklist_id: uuid.UUID
    event_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True)
class BudgetLineAdded:
    budget_line_id: uuid.UUID
    event_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True)
class GuestAdded:
    guest_id: uuid.UUID
    event_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True)
class TimelineBlockAdded:
    block_id: uuid.UUID
    event_id: uuid.UUID
    occurred_at: datetime