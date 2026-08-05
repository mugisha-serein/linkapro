import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GuestAdded:
    guest_id: uuid.UUID
    event_id: uuid.UUID
    occurred_at: datetime

