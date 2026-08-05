from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from domain.events.timeline.entity import TimelineBlock


class ITimelineBlockRepository(ABC):
    @abstractmethod
    def get_by_id(self, block_id: uuid.UUID) -> Optional[TimelineBlock]: ...

    @abstractmethod
    def list_by_event(self, event_id: uuid.UUID) -> List[TimelineBlock]: ...

    @abstractmethod
    def save(self, block: TimelineBlock) -> TimelineBlock: ...

    @abstractmethod
    def delete(self, block_id: uuid.UUID) -> None: ...

