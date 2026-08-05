import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.shared.utils import utc_now


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

