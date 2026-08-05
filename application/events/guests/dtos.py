from dataclasses import dataclass
from typing import List, Optional
import uuid


@dataclass(frozen=True)
class GuestEntryDTO:
    id: uuid.UUID
    event_id: uuid.UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    rsvp_status: str
    dietary_restrictions: List[str]
    plus_one: bool
    table_assignment: Optional[str]
    notes: Optional[str]

