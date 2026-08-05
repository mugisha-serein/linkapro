from domain.events.event.entity import Event

from application.events.event.dtos import EventDTO


def to_event_dto(e: Event, vendors_count: int = 0, progress_percent: float = 0.0) -> EventDTO:
    return EventDTO(
        id=e.id,
        planner_id=e.planner_id,
        name=e.name,
        event_type=e.event_type.value,
        event_date=e.event_date,
        venue=e.venue,
        expected_guests=e.expected_guests,
        total_budget=float(e.total_budget.amount),
        created_at=e.created_at,
        updated_at=e.updated_at,
        vendors_count=vendors_count,
        progress_percent=progress_percent,
    )
