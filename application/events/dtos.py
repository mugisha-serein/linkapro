"""DTOs for event planning."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List
import uuid


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
class ChecklistDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class ChecklistItemDTO:
    id: uuid.UUID
    checklist_id: uuid.UUID
    description: str
    status: str
    due_date: Optional[date]
    assigned_to: Optional[str]
    order: int


@dataclass(frozen=True)
class BudgetLineDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    category: str
    description: str
    estimated_cost: float
    actual_cost: Optional[float]
    notes: Optional[str]


@dataclass(frozen=True)
class GuestEntryDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    rsvp_status: str
    dietary_restrictions: List[str]
    plus_one: bool
    table_assignment: Optional[str]
    notes: Optional[str]


@dataclass(frozen=True)
class TimelineBlockDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str]
    location: Optional[str]
    order: int


@dataclass(frozen=True)
class DashboardSummaryDTO:
    active_events_count: int
    open_tasks_count: int
    budget_usage_percent: float
    vendors_linked_count: int
    upcoming_events: List[EventDTO]
    recent_tasks: List[ChecklistItemDTO]