from typing import List, Optional
import uuid

from domain.events.event.entity import Event
from domain.events.event.interfaces import IEventRepository

from application.events.event.dtos import EventDTO
from application.events.event.mappers import to_event_dto


class EventQueryHandlers:
    def __init__(self, event_repo: IEventRepository):
        self.event_repo = event_repo

    def get_event(self, event_id: uuid.UUID) -> Optional[Event]:
        return self.event_repo.get_by_id(event_id)

    def list_events_by_planner(self, planner_id: uuid.UUID) -> List[Event]:
        return self.event_repo.list_by_planner(planner_id)

    def to_event_dto(self, event: Event, vendors_count: int = 0, progress_percent: float = 0.0) -> EventDTO:
        return to_event_dto(event, vendors_count=vendors_count, progress_percent=progress_percent)

