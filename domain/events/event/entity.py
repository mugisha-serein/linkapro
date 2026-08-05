import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from domain.events.event.value_objects import EventType
from domain.shared.utils import utc_now


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

    def update_details(
        self,
        name: Optional[str] = None,
        event_type: Optional[EventType] = None,
        event_date: Optional[date] = None,
        venue: Optional[str] = None,
        expected_guests: Optional[int] = None,
        total_budget: Optional[float] = None,
    ) -> None:
        if name is not None:
            self.name = name
        if event_type is not None:
            self.event_type = event_type
        if event_date is not None:
            self.event_date = event_date
        if venue is not None:
            self.venue = venue
        if expected_guests is not None:
            self.expected_guests = expected_guests
        if total_budget is not None:
            self.total_budget = total_budget
        self.updated_at = utc_now()

