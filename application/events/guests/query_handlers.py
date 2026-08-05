from typing import List
import uuid

from domain.events.guests.interfaces import IGuestEntryRepository

from application.events.guests.dtos import GuestEntryDTO
from application.events.guests.mappers import to_guest_dto


class GuestQueryHandlers:
    def __init__(self, guest_repo: IGuestEntryRepository):
        self.guest_repo = guest_repo

    def list_guests(self, event_id: uuid.UUID) -> List[GuestEntryDTO]:
        guests = self.guest_repo.list_by_event(event_id)
        return [to_guest_dto(guest) for guest in guests]

