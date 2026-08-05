"""Command and query handlers for events."""
import uuid
from datetime import datetime, date
from typing import Optional, List

from domain.events.entities import (
    Event, Checklist, ChecklistItem, BudgetLine, GuestEntry, TimelineBlock,
    ChecklistItemStatus
)
from domain.events.interfaces import (
    IEventRepository, IChecklistRepository, IChecklistItemRepository,
    IBudgetLineRepository, IGuestEntryRepository, ITimelineBlockRepository
)
from application.events.budget.command_handlers import BudgetCommandHandlers
from application.events.budget.mappers import to_budget_dto
from application.events.budget.query_handlers import BudgetQueryHandlers
from application.events.checklists.command_handlers import ChecklistCommandHandlers
from application.events.checklists.mappers import to_checklist_dto, to_checklist_item_dto
from application.events.checklists.query_handlers import ChecklistQueryHandlers
from application.events.event.command_handlers import EventCommandHandlers as EventOnlyCommandHandlers
from application.events.event.mappers import to_event_dto
from application.events.event.query_handlers import EventQueryHandlers as EventOnlyQueryHandlers
from application.events.guests.command_handlers import GuestCommandHandlers
from application.events.guests.mappers import to_guest_dto
from application.events.guests.query_handlers import GuestQueryHandlers
from application.events.timeline.command_handlers import TimelineCommandHandlers
from application.events.timeline.mappers import to_timeline_dto
from application.events.timeline.query_handlers import TimelineQueryHandlers
from .commands import (
    CreateEventCommand, UpdateEventCommand, DeleteEventCommand,
    CreateChecklistCommand, AddChecklistItemCommand, UpdateChecklistItemCommand,
    AddBudgetLineCommand, UpdateBudgetLineCommand,
    AddGuestCommand, UpdateGuestCommand,
    AddTimelineBlockCommand,
)
from .dtos import (
    EventDTO, ChecklistDTO, ChecklistItemDTO, BudgetLineDTO,
    GuestEntryDTO, TimelineBlockDTO, DashboardSummaryDTO
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
        self.event_handlers = EventOnlyCommandHandlers(event_repo, event_dispatcher)
        self.checklist_handlers = ChecklistCommandHandlers(checklist_repo, checklist_item_repo, event_dispatcher)
        self.budget_handlers = BudgetCommandHandlers(budget_repo, event_dispatcher)
        self.guest_handlers = GuestCommandHandlers(guest_repo, event_dispatcher)
        self.timeline_handlers = TimelineCommandHandlers(timeline_repo, event_dispatcher)

    def create_event(self, cmd: CreateEventCommand) -> EventDTO:
        return self.event_handlers.create_event(cmd)

    def update_event(self, cmd: UpdateEventCommand) -> EventDTO:
        return self.event_handlers.update_event(cmd)

    def delete_event(self, cmd: DeleteEventCommand) -> None:
        self.event_repo.delete(cmd.event_id)

    def create_checklist(self, cmd: CreateChecklistCommand) -> ChecklistDTO:
        return self.checklist_handlers.create_checklist(cmd)

    def add_checklist_item(self, cmd: AddChecklistItemCommand) -> ChecklistItemDTO:
        return self.checklist_handlers.add_checklist_item(cmd)

    def update_checklist_item(self, cmd: UpdateChecklistItemCommand) -> ChecklistItemDTO:
        return self.checklist_handlers.update_checklist_item(cmd)

    def add_budget_line(self, cmd: AddBudgetLineCommand) -> BudgetLineDTO:
        return self.budget_handlers.add_budget_line(cmd)

    def update_budget_line(self, cmd: UpdateBudgetLineCommand) -> BudgetLineDTO:
        return self.budget_handlers.update_budget_line(cmd)

    def add_guest(self, cmd: AddGuestCommand) -> GuestEntryDTO:
        return self.guest_handlers.add_guest(cmd)

    def update_guest(self, cmd: UpdateGuestCommand) -> GuestEntryDTO:
        return self.guest_handlers.update_guest(cmd)

    def add_timeline_block(self, cmd: AddTimelineBlockCommand) -> TimelineBlockDTO:
        return self.timeline_handlers.add_timeline_block(cmd)

    # DTO converters
    @staticmethod
    def _to_event_dto(e: Event, vendors_count: int = 0, progress_percent: float = 0.0) -> EventDTO:
        return to_event_dto(e, vendors_count=vendors_count, progress_percent=progress_percent)

    @staticmethod
    def _to_checklist_dto(c: Checklist) -> ChecklistDTO:
        return to_checklist_dto(c)

    @staticmethod
    def _to_item_dto(i: ChecklistItem) -> ChecklistItemDTO:
        return to_checklist_item_dto(i)

    @staticmethod
    def _to_budget_dto(b: BudgetLine) -> BudgetLineDTO:
        return to_budget_dto(b)

    @staticmethod
    def _to_guest_dto(g: GuestEntry) -> GuestEntryDTO:
        return to_guest_dto(g)

    @staticmethod
    def _to_timeline_dto(t: TimelineBlock) -> TimelineBlockDTO:
        return to_timeline_dto(t)
    
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
        self.event_query_handlers = EventOnlyQueryHandlers(event_repo)
        self.checklist_query_handlers = ChecklistQueryHandlers(checklist_repo, checklist_item_repo)
        self.budget_query_handlers = BudgetQueryHandlers(budget_repo)
        self.guest_query_handlers = GuestQueryHandlers(guest_repo)
        self.timeline_query_handlers = TimelineQueryHandlers(timeline_repo)

    def get_event(self, event_id: uuid.UUID) -> Optional[EventDTO]:
        event = self.event_query_handlers.get_event(event_id)
        if not event:
            return None
        return self._enrich_event(event)

    def list_events_by_planner(self, planner_id: uuid.UUID) -> List[EventDTO]:
        events = self.event_query_handlers.list_events_by_planner(planner_id)
        return [self._enrich_event(e) for e in events]

    def _enrich_event(self, e: Event) -> EventDTO:
        # Calculate progress from checklist items
        checklists = self.checklist_repo.list_by_event(e.id)
        total_items = 0
        completed_items = 0
        for cl in checklists:
            items = self.checklist_item_repo.list_by_checklist(cl.id)
            total_items += len(items)
            completed_items += len([i for i in items if i.status == ChecklistItemStatus.COMPLETED])
        
        progress = (completed_items / total_items * 100) if total_items > 0 else 0.0
        
        return EventCommandHandlers._to_event_dto(
            e, 
            vendors_count=0, # Placeholder
            progress_percent=round(progress, 1)
        )

    def get_checklist(self, checklist_id: uuid.UUID) -> Optional[ChecklistDTO]:
        return self.checklist_query_handlers.get_checklist(checklist_id)

    def list_checklists_by_event(self, event_id: uuid.UUID) -> List[ChecklistDTO]:
        return self.checklist_query_handlers.list_checklists_by_event(event_id)

    def list_checklist_items(self, checklist_id: uuid.UUID) -> List[ChecklistItemDTO]:
        return self.checklist_query_handlers.list_checklist_items(checklist_id)

    def list_budget_lines(self, event_id: uuid.UUID) -> List[BudgetLineDTO]:
        return self.budget_query_handlers.list_budget_lines(event_id)

    def list_guests(self, event_id: uuid.UUID) -> List[GuestEntryDTO]:
        return self.guest_query_handlers.list_guests(event_id)

    def list_timeline_blocks(self, event_id: uuid.UUID) -> List[TimelineBlockDTO]:
        return self.timeline_query_handlers.list_timeline_blocks(event_id)

    def get_dashboard_summary(self, planner_id: uuid.UUID) -> DashboardSummaryDTO:
        events = self.list_events_by_planner(planner_id)
        active_events_count = len(events)
        
        open_tasks = []
        total_estimated = 0.0
        total_actual = 0.0
        
        for event in events:
            # Tasks
            checklists = self.list_checklists_by_event(event.id)
            for cl in checklists:
                items = self.list_checklist_items(cl.id)
                open_tasks.extend([i for i in items if i.status != "completed"])
            
            # Budget
            lines = self.list_budget_lines(event.id)
            for line in lines:
                total_estimated += float(line.estimated_cost)
                total_actual += float(line.actual_cost) if line.actual_cost is not None else 0.0
        
        budget_usage = (total_actual / total_estimated * 100) if total_estimated > 0 else 0.0
        
        # Sort events by date
        sorted_events = sorted(events, key=lambda x: x.event_date)
        upcoming = sorted_events[:3]
        
        # Sort tasks by due date (if any) or just take first 5
        recent_tasks = sorted(open_tasks, key=lambda x: x.due_date if x.due_date else date.max)[:5]
        
        return DashboardSummaryDTO(
            active_events_count=active_events_count,
            open_tasks_count=len(open_tasks),
            budget_usage_percent=round(budget_usage, 1),
            vendors_linked_count=0,
            upcoming_events=upcoming,
            recent_tasks=recent_tasks,
        )
