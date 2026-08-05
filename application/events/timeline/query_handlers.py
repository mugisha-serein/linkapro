from typing import List
import uuid

from domain.events.timeline.interfaces import ITimelineBlockRepository

from application.events.timeline.dtos import TimelineBlockDTO
from application.events.timeline.mappers import to_timeline_dto


class TimelineQueryHandlers:
    def __init__(self, timeline_repo: ITimelineBlockRepository):
        self.timeline_repo = timeline_repo

    def list_timeline_blocks(self, event_id: uuid.UUID) -> List[TimelineBlockDTO]:
        blocks = self.timeline_repo.list_by_event(event_id)
        return [to_timeline_dto(block) for block in blocks]

