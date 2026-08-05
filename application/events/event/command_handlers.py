"""Event-only command handlers for the event planning application layer."""

import uuid

from domain.events.domain_events import EventCreated
from domain.events.event.entity import Event
from domain.events.event.errors import EventNotFound
from domain.events.event.interfaces import IEventRepository
from domain.events.event.value_objects import EventType
from domain.shared.utils import utc_now

from application.events.commands import CreateEventCommand, UpdateEventCommand
from application.events.dtos import EventDTO


class EventCommandHandlers:
    def __init__(self, event_repo: IEventRepository, event_dispatcher):
        self.event_repo = event_repo
        self.event_dispatcher = event_dispatcher

    def create_event(self, cmd: CreateEventCommand) -> EventDTO:
        event = Event(
            id=uuid.uuid4(),
            planner_id=cmd.planner_id,
            name=cmd.name,
            event_type=EventType(cmd.event_type),
            event_date=cmd.event_date,
            venue=cmd.venue,
            expected_guests=cmd.expected_guests,
            total_budget=cmd.total_budget,
        )
        saved = self.event_repo.save(event)
        self.event_dispatcher.dispatch(
            EventCreated(event_id=saved.id, planner_id=saved.planner_id, occurred_at=utc_now())
        )
        return self._to_event_dto(saved)

    def update_event(self, cmd: UpdateEventCommand) -> EventDTO:
        event = self.event_repo.get_by_id(cmd.event_id)
        if not event:
            raise EventNotFound("Event not found")
        event.update_details(
            name=cmd.name,
            event_type=EventType(cmd.event_type) if cmd.event_type is not None else None,
            event_date=cmd.event_date,
            venue=cmd.venue,
            expected_guests=cmd.expected_guests,
            total_budget=cmd.total_budget,
        )
        saved = self.event_repo.save(event)
        return self._to_event_dto(saved)

    @staticmethod
    def _to_event_dto(e: Event, vendors_count: int = 0, progress_percent: float = 0.0) -> EventDTO:
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
