"""Commands for event planning module."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List
import uuid

from domain.events.entities import EventType, BudgetCategory, RSVPStatus, DietaryRestriction


@dataclass(frozen=True)
class CreateEventCommand:
    planner_id: uuid.UUID
    name: str
    event_type: str
    event_date: date
    venue: Optional[str] = None
    expected_guests: int = 0
    total_budget: float = 0.0


@dataclass(frozen=True)
class UpdateEventCommand:
    event_id: uuid.UUID
    name: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[date] = None
    venue: Optional[str] = None
    expected_guests: Optional[int] = None
    total_budget: Optional[float] = None


@dataclass(frozen=True)
class DeleteEventCommand:
    event_id: uuid.UUID


@dataclass(frozen=True)
class CreateChecklistCommand:
    event_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class AddChecklistItemCommand:
    checklist_id: uuid.UUID
    description: str
    due_date: Optional[date] = None
    assigned_to: Optional[str] = None


@dataclass(frozen=True)
class UpdateChecklistItemCommand:
    item_id: uuid.UUID
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to: Optional[str] = None


@dataclass(frozen=True)
class AddBudgetLineCommand:
    event_id: uuid.UUID
    category: str
    description: str
    estimated_cost: float
    actual_cost: Optional[float] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class UpdateBudgetLineCommand:
    line_id: uuid.UUID
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class AddGuestCommand:
    event_id: uuid.UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    dietary_restrictions: List[str] = field(default_factory=list)
    plus_one: bool = False
    notes: Optional[str] = None


@dataclass(frozen=True)
class UpdateGuestCommand:
    guest_id: uuid.UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    rsvp_status: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    plus_one: Optional[bool] = None
    table_assignment: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class AddTimelineBlockCommand:
    event_id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
