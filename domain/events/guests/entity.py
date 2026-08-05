import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from domain.events.guests.errors import InvalidGuestEntry
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

    def __post_init__(self) -> None:
        self._validate_full_name(self.full_name)

    def update_rsvp(self, status: RSVPStatus) -> None:
        self.rsvp_status = status
        self.updated_at = utc_now()

    def assign_table(self, table_name: str) -> None:
        self.table_assignment = table_name
        self.updated_at = utc_now()

    def update_contact(
        self,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> None:
        changed = False
        if full_name is not None:
            self._validate_full_name(full_name)
            self.full_name = full_name
            changed = True
        if email is not None:
            self.email = email
            changed = True
        if phone is not None:
            self.phone = phone
            changed = True
        if changed:
            self.updated_at = utc_now()

    @staticmethod
    def _validate_full_name(full_name: str) -> None:
        if not isinstance(full_name, str) or not full_name.strip():
            raise InvalidGuestEntry("Guest full name must not be blank")
