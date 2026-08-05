from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


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

