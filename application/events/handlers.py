"""Command and query handlers for events."""
import uuid
from datetime import datetime
from typing import Optional, List

from domain.shared.utils import utc_now
from domain.events.entities import (
    Event, Checklist, ChecklistItem, BudgetLine, GuestEntry, TimelineBlock,
    EventType, BudgetCategory, RSVPStatus, DietaryRestriction, ChecklistItemStatus
)
from domain.events.interfaces import (
    IEventRepository, IChecklistRepository, IChecklistItemRepository,
    IBudgetLineRepository, IGuestEntryRepository, ITimelineBlockRepository
)
from domain.events.events import (
    EventCreated, ChecklistCreated, BudgetLineAdded, GuestAdded, TimelineBlockAdded
)
from .commands import (
    CreateEventCommand, UpdateEventCommand, DeleteEventCommand,
    CreateChecklistCommand, AddChecklistItemCommand, UpdateChecklistItemCommand,
    AddBudgetLineCommand, UpdateBudgetLineCommand,
    AddGuestCommand, UpdateGuestCommand,
    AddTimelineBlockCommand,
)
from .dtos import (
    EventDTO, ChecklistDTO, ChecklistItemDTO, BudgetLineDTO,
    GuestEntryDTO, TimelineBlockDTO
)


class EventCommandHandlers:
    def __init__(
        self,
        event_repo: IEventRepository,
        checklist_repo: IChecklistRepository,
        checklist_item_repo: IChecklistItemRepository,
        budget_repo: IBudgetLineRepository,
        guest_repo: IGuestEntryRepository,
        timeline_repo: ITimelineBlockRepository,
        event_dispatcher,
    ):
        self.event_repo = event_repo
        self.checklist_repo = checklist_repo
        self.checklist_item_repo = checklist_item_repo
        self.budget_repo = budget_repo
        self.guest_repo = guest_repo
        self.timeline_repo = timeline_repo
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
            raise ValueError("Event not found")
        event.update_details(
            name=cmd.name,
            venue=cmd.venue,
            expected_guests=cmd.expected_guests,
            total_budget=cmd.total_budget,
        )
        saved = self.event_repo.save(event)
        return self._to_event_dto(saved)

    def delete_event(self, cmd: DeleteEventCommand) -> None:
        self.event_repo.delete(cmd.event_id)

    def create_checklist(self, cmd: CreateChecklistCommand) -> ChecklistDTO:
        checklist = Checklist(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            name=cmd.name,
        )
        saved = self.checklist_repo.save(checklist)
        self.event_dispatcher.dispatch(
            ChecklistCreated(checklist_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_checklist_dto(saved)

    def add_checklist_item(self, cmd: AddChecklistItemCommand) -> ChecklistItemDTO:
        # Determine max order
        existing = self.checklist_item_repo.list_by_checklist(cmd.checklist_id)
        max_order = max([i.order for i in existing], default=-1)
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=cmd.checklist_id,
            description=cmd.description,
            due_date=cmd.due_date,
            assigned_to=cmd.assigned_to,
            order=max_order + 1,
        )
        saved = self.checklist_item_repo.save(item)
        return self._to_item_dto(saved)

    def update_checklist_item(self, cmd: UpdateChecklistItemCommand) -> ChecklistItemDTO:
        item = self.checklist_item_repo.get_by_id(cmd.item_id)
        if not item:
            raise ValueError("Checklist item not found")
        if cmd.description is not None:
            item.description = cmd.description
        if cmd.status is not None:
            item.status = ChecklistItemStatus(cmd.status)
        if cmd.due_date is not None:
            item.due_date = cmd.due_date
        if cmd.assigned_to is not None:
            item.assigned_to = cmd.assigned_to
        saved = self.checklist_item_repo.save(item)
        return self._to_item_dto(saved)

    def add_budget_line(self, cmd: AddBudgetLineCommand) -> BudgetLineDTO:
        line = BudgetLine(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            category=BudgetCategory(cmd.category),
            description=cmd.description,
            estimated_cost=cmd.estimated_cost,
            actual_cost=cmd.actual_cost,
            notes=cmd.notes,
        )
        saved = self.budget_repo.save(line)
        self.event_dispatcher.dispatch(
            BudgetLineAdded(budget_line_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_budget_dto(saved)

    def update_budget_line(self, cmd: UpdateBudgetLineCommand) -> BudgetLineDTO:
        line = self.budget_repo.get_by_id(cmd.line_id)
        if not line:
            raise ValueError("Budget line not found")
        if cmd.estimated_cost is not None:
            line.estimated_cost = cmd.estimated_cost
        if cmd.actual_cost is not None:
            line.actual_cost = cmd.actual_cost
        if cmd.notes is not None:
            line.notes = cmd.notes
        saved = self.budget_repo.save(line)
        return self._to_budget_dto(saved)

    def add_guest(self, cmd: AddGuestCommand) -> GuestEntryDTO:
        restrictions = [DietaryRestriction(r) for r in cmd.dietary_restrictions]
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=cmd.event_id,
            full_name=cmd.full_name,
            email=cmd.email,
            phone=cmd.phone,
            dietary_restrictions=restrictions,
            plus_one=cmd.plus_one,
            notes=cmd.notes,
        )
        saved = self.guest_repo.save(guest)
        self.event_dispatcher.dispatch(
            GuestAdded(guest_id=saved.id, event_id=saved.event_id, occurred_at=utc_now())
        )
        return self._to_guest_dto(saved)

    def update_guest(self, cmd: UpdateGuestCommand) -> GuestEntryDTO:
        guest = self.guest_repo.get_by_id(cmd.guest_id)
        if not guest:
            raise ValueError("Guest not found")
        if cmd.full_name is not None:
            guest.full_name = cmd.full_name
        if cmd.email is not None:
            guest.email = cmd.email
        if cmd.phone is not None:
            guest.phone = cmd.phone
        if cmd.rsvp_status is not None:
            guest.rsvp_status = RSVPStatus(cmd.rsvp_status)
        if cmd.dietary_restrictions is not None:
            guest.dietary_restrictions = [DietaryRestriction(r) for r in cmd.dietary_restrictions]
        if cmd.plus_one is not None:
            guest.plus_one = cmd.plus_one
        if cmd.table_assignment is not None:
            guest.table_assignment = cmd.table_assignment
        if cmd.notes is not None:
            guest.notes = cmd.notes
        saved = self.guest_repo.save(guest)
        return self._to_guest_dto(saved)

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

    # DTO converters
    @staticmethod
    def _to_event_dto(e: Event) -> EventDTO:
        return EventDTO(
            id=e.id, planner_id=e.planner_id, name=e.name, event_type=e.event_type.value,
            event_date=e.event_date, venue=e.venue, expected_guests=e.expected_guests,
            total_budget=e.total_budget, created_at=e.created_at, updated_at=e.updated_at,
        )

    @staticmethod
    def _to_checklist_dto(c: Checklist) -> ChecklistDTO:
        return ChecklistDTO(id=c.id, event_id=c.event_id, name=c.name)

    @staticmethod
    def _to_item_dto(i: ChecklistItem) -> ChecklistItemDTO:
        return ChecklistItemDTO(
            id=i.id, checklist_id=i.checklist_id, description=i.description,
            status=i.status.value, due_date=i.due_date, assigned_to=i.assigned_to, order=i.order,
        )

    @staticmethod
    def _to_budget_dto(b: BudgetLine) -> BudgetLineDTO:
        return BudgetLineDTO(
            id=b.id, event_id=b.event_id, category=b.category.value, description=b.description,
            estimated_cost=b.estimated_cost, actual_cost=b.actual_cost, notes=b.notes,
        )

    @staticmethod
    def _to_guest_dto(g: GuestEntry) -> GuestEntryDTO:
        return GuestEntryDTO(
            id=g.id, event_id=g.event_id, full_name=g.full_name, email=g.email, phone=g.phone,
            rsvp_status=g.rsvp_status.value,
            dietary_restrictions=[r.value for r in g.dietary_restrictions],
            plus_one=g.plus_one, table_assignment=g.table_assignment, notes=g.notes,
        )

    @staticmethod
    def _to_timeline_dto(t: TimelineBlock) -> TimelineBlockDTO:
        return TimelineBlockDTO(
            id=t.id, event_id=t.event_id, title=t.title, start_time=t.start_time,
            end_time=t.end_time, description=t.description, location=t.location, order=t.order,
        )
    
class EventQueryHandlers:
    """Read-only queries for events."""
    
    def __init__(
        self,
        event_repo: IEventRepository,
        checklist_repo: IChecklistRepository,
        checklist_item_repo: IChecklistItemRepository,
        budget_repo: IBudgetLineRepository,
        guest_repo: IGuestEntryRepository,
        timeline_repo: ITimelineBlockRepository,
    ):
        self.event_repo = event_repo
        self.checklist_repo = checklist_repo
        self.checklist_item_repo = checklist_item_repo
        self.budget_repo = budget_repo
        self.guest_repo = guest_repo
        self.timeline_repo = timeline_repo

    def get_event(self, event_id: uuid.UUID) -> Optional[EventDTO]:
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return None
        return EventCommandHandlers._to_event_dto(event)

    def list_events_by_planner(self, planner_id: uuid.UUID) -> List[EventDTO]:
        events = self.event_repo.list_by_planner(planner_id)
        return [EventCommandHandlers._to_event_dto(e) for e in events]

    def get_checklist(self, checklist_id: uuid.UUID) -> Optional[ChecklistDTO]:
        checklist = self.checklist_repo.get_by_id(checklist_id)
        if not checklist:
            return None
        return EventCommandHandlers._to_checklist_dto(checklist)

    def list_checklists_by_event(self, event_id: uuid.UUID) -> List[ChecklistDTO]:
        checklists = self.checklist_repo.list_by_event(event_id)
        return [EventCommandHandlers._to_checklist_dto(c) for c in checklists]

    def list_checklist_items(self, checklist_id: uuid.UUID) -> List[ChecklistItemDTO]:
        items = self.checklist_item_repo.list_by_checklist(checklist_id)
        return [EventCommandHandlers._to_item_dto(i) for i in items]

    def list_budget_lines(self, event_id: uuid.UUID) -> List[BudgetLineDTO]:
        lines = self.budget_repo.list_by_event(event_id)
        return [EventCommandHandlers._to_budget_dto(l) for l in lines]

    def list_guests(self, event_id: uuid.UUID) -> List[GuestEntryDTO]:
        guests = self.guest_repo.list_by_event(event_id)
        return [EventCommandHandlers._to_guest_dto(g) for g in guests]

    def list_timeline_blocks(self, event_id: uuid.UUID) -> List[TimelineBlockDTO]:
        blocks = self.timeline_repo.list_by_event(event_id)
        return [EventCommandHandlers._to_timeline_dto(b) for b in blocks]