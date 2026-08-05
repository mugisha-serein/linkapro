from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
import uuid

from application.events.checklists.dtos import ChecklistItemDTO


@dataclass(frozen=True)
class EventDTO:
    id: uuid.UUID
    planner_id: uuid.UUID
    name: str
    event_type: str
    event_date: date
    venue: Optional[str]
    expected_guests: int
    total_budget: float
    created_at: datetime
    updated_at: datetime
    vendors_count: int = 0
    progress_percent: float = 0.0


@dataclass(frozen=True)
class DashboardSummaryDTO:
    active_events_count: int
    open_tasks_count: int
    budget_usage_percent: float
    vendors_linked_count: int
    upcoming_events: List[EventDTO]
    recent_tasks: List[ChecklistItemDTO]

