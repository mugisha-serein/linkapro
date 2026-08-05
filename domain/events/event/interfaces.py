from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from domain.events.event.entity import Event


class IEventRepository(ABC):
    @abstractmethod
    def get_by_id(self, event_id: uuid.UUID) -> Optional[Event]: ...

    @abstractmethod
    def list_by_planner(self, planner_id: uuid.UUID) -> List[Event]: ...

    @abstractmethod
    def save(self, event: Event) -> Event: ...

    @abstractmethod
    def delete(self, event_id: uuid.UUID) -> None: ...

