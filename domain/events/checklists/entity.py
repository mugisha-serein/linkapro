import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.shared.utils import utc_now


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

