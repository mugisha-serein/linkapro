import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EventCreated:
    event_id: uuid.UUID
    planner_id: uuid.UUID
    occurred_at: datetime

