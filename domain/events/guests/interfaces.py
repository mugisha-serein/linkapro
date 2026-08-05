from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from domain.events.guests.entity import GuestEntry


class IGuestEntryRepository(ABC):
    @abstractmethod
    def get_by_id(self, guest_id: uuid.UUID) -> Optional[GuestEntry]: ...

    @abstractmethod
    def list_by_event(self, event_id: uuid.UUID) -> List[GuestEntry]: ...

    @abstractmethod
    def save(self, guest: GuestEntry) -> GuestEntry: ...

    @abstractmethod
    def delete(self, guest_id: uuid.UUID) -> None: ...

