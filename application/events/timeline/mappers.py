from domain.events.timeline.entity import TimelineBlock

from application.events.timeline.dtos import TimelineBlockDTO


def to_timeline_dto(t: TimelineBlock) -> TimelineBlockDTO:
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

