"""Timeline command handlers for the event planning application layer."""

import uuid

from domain.events.domain_events import TimelineBlockAdded
from domain.events.timeline.entity import TimelineBlock
from domain.events.timeline.interfaces import ITimelineBlockRepository
from domain.shared.utils import utc_now

from application.events.commands import AddTimelineBlockCommand
from application.events.dtos import TimelineBlockDTO


class TimelineCommandHandlers:
    def __init__(self, timeline_repo: ITimelineBlockRepository, event_dispatcher):
        self.timeline_repo = timeline_repo
        self.event_dispatcher = event_dispatcher

    def add_timeline_block(self, cmd: AddTimelineBlockCommand) -> TimelineBlockDTO:
        existing = self.timeline_repo.list_by_event(cmd.event_id)
        max_order = max([b.order for b in existing], default=-1)
        block = TimelineBlock(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            title=cmd.title,
            start_time=cmd.start_time,
            end_time=cmd.end_time,
            description=cmd.description,
            location=cmd.location,
            order=max_order + 1,
        )
        saved = self.timeline_repo.save(block)
        self.event_dispatcher.dispatch(
            TimelineBlockAdded(block_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_timeline_dto(saved)

    @staticmethod
    def _to_timeline_dto(t: TimelineBlock) -> TimelineBlockDTO:
        return TimelineBlockDTO(
            id=t.id,
            event_id=t.event_id,
            title=t.title,
            start_time=t.start_time,
            end_time=t.end_time,
            description=t.description,
            location=t.location,
            order=t.order,
        )

