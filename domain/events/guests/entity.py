import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from domain.events.guests.value_objects import DietaryRestriction, RSVPStatus
from domain.shared.utils import utc_now


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

