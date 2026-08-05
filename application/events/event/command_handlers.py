"""Event-only command handlers for the event planning application layer."""

import logging
import uuid

from domain.events.domain_events import EventCreated
from domain.events.event.entity import Event
from domain.events.event.errors import EventNotFound
from domain.events.event.interfaces import IEventRepository
from domain.events.event.value_objects import EventType
from domain.shared.utils import utc_now

from application.events.commands import CreateEventCommand, UpdateEventCommand
from application.events.dtos import EventDTO

logger = logging.getLogger(__name__)


class EventCommandHandlers:
    def __init__(self, event_repo: IEventRepository, event_dispatcher):
        self.event_repo = event_repo
        self.event_dispatcher = event_dispatcher

    def create_event(self, cmd: CreateEventCommand) -> EventDTO:
        event = Event.create(
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
        recorded_events = event.pull_events()
        manual_event = self._manual_event_created(saved, recorded_events)
        self._log_recorded_event_comparison(manual_event, recorded_events)
        self.event_dispatcher.dispatch(manual_event)
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

    @staticmethod
    def _manual_event_created(saved: Event, recorded_events: list[object]) -> EventCreated:
        recorded_event = recorded_events[0] if len(recorded_events) == 1 else None
        occurred_at = recorded_event.occurred_at if isinstance(recorded_event, EventCreated) else utc_now()
        return EventCreated(event_id=saved.id, planner_id=saved.planner_id, occurred_at=occurred_at)

    @staticmethod
    def _log_recorded_event_comparison(manual_event: EventCreated, recorded_events: list[object]) -> None:
        if recorded_events != [manual_event]:
            logger.warning(
                "Event aggregate recorded events differ from manual dispatch event",
                extra={
                    "manual_event_type": type(manual_event).__name__,
                    "recorded_event_types": [type(event).__name__ for event in recorded_events],
                    "event_id": str(manual_event.event_id),
                },
            )
