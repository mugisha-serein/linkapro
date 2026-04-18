"""Event planning domain entities."""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List

from domain.shared.utils import utc_now


class EventType(str, Enum):
    WEDDING = "wedding"
    TRAVEL = "travel"
    CORPORATE = "corporate"
    OTHER = "other"


class ChecklistItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class BudgetCategory(str, Enum):
    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    DECOR = "decor"
    ENTERTAINMENT = "entertainment"
    TRANSPORTATION = "transportation"
    ATTIRE = "attire"
    OTHER = "other"


class RSVPStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    MAYBE = "maybe"


class DietaryRestriction(str, Enum):
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    HALAL = "halal"
    KOSHER = "kosher"
    OTHER = "other"


@dataclass
class Event:
    """Main event entity owned by a planner."""
    id: uuid.UUID
    planner_id: uuid.UUID
    name: str
    event_type: EventType
    event_date: date
    venue: Optional[str] = None
    expected_guests: int = 0
    total_budget: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_details(self, name: Optional[str] = None, venue: Optional[str] = None, 
                       expected_guests: Optional[int] = None, total_budget: Optional[float] = None) -> None:
        if name is not None:
            self.name = name
        if venue is not None:
            self.venue = venue
        if expected_guests is not None:
            self.expected_guests = expected_guests
        if total_budget is not None:
            self.total_budget = total_budget
        self.updated_at = utc_now()


@dataclass
class Checklist:
    """A checklist associated with an event."""
    id: uuid.UUID
    event_id: uuid.UUID
    name: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def rename(self, new_name: str) -> None:
        self.name = new_name
        self.updated_at = utc_now()


@dataclass
class ChecklistItem:
    """Individual task within a checklist."""
    id: uuid.UUID
    checklist_id: uuid.UUID
    description: str
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    due_date: Optional[date] = None
    assigned_to: Optional[str] = None
    order: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def mark_completed(self) -> None:
        self.status = ChecklistItemStatus.COMPLETED
        self.updated_at = utc_now()

    def mark_in_progress(self) -> None:
        self.status = ChecklistItemStatus.IN_PROGRESS
        self.updated_at = utc_now()

    def update_description(self, new_desc: str) -> None:
        self.description = new_desc
        self.updated_at = utc_now()


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


@dataclass
class GuestEntry:
    """Guest in the guest list."""
    id: uuid.UUID
    event_id: uuid.UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    rsvp_status: RSVPStatus = RSVPStatus.PENDING
    dietary_restrictions: List[DietaryRestriction] = field(default_factory=list)
    plus_one: bool = False
    table_assignment: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_rsvp(self, status: RSVPStatus) -> None:
        self.rsvp_status = status
        self.updated_at = utc_now()

    def assign_table(self, table_name: str) -> None:
        self.table_assignment = table_name
        self.updated_at = utc_now()


@dataclass
class TimelineBlock:
    """A block in the event timeline (drag-and-drop)."""
    id: uuid.UUID
    event_id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    order: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def reschedule(self, start: datetime, end: datetime) -> None:
        if start >= end:
            raise ValueError("End time must be after start time")
        self.start_time = start
        self.end_time = end
        self.updated_at = utc_now()