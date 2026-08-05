import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.events.timeline.errors import InvalidTimelineRange
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

    def __post_init__(self) -> None:
        self._validate_range(self.start_time, self.end_time)

    def reschedule(self, start: datetime, end: datetime) -> None:
        self._validate_range(start, end)
        self.start_time = start
        self.end_time = end
        self.updated_at = utc_now()

    @staticmethod
    def _validate_range(start: datetime, end: datetime) -> None:
        if start >= end:
            raise InvalidTimelineRange("End time must be after start time")
