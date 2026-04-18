from infrastructure.repos.django_event_repository import DjangoEventRepository
from infrastructure.repos.django_checklist_repository import DjangoChecklistRepository
from infrastructure.repos.django_checklist_item_repository import DjangoChecklistItemRepository
from infrastructure.repos.django_budget_line_repository import DjangoBudgetLineRepository
from infrastructure.repos.django_guest_entry_repository import DjangoGuestEntryRepository
from infrastructure.repos.django_timeline_block_repository import DjangoTimelineBlockRepository
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher
from application.events.handlers import EventCommandHandlers, EventQueryHandlers


def get_command_handlers():
    return EventCommandHandlers(
        event_repo=DjangoEventRepository(),
        checklist_repo=DjangoChecklistRepository(),
        checklist_item_repo=DjangoChecklistItemRepository(),
        budget_repo=DjangoBudgetLineRepository(),
        guest_repo=DjangoGuestEntryRepository(),
        timeline_repo=DjangoTimelineBlockRepository(),
        event_dispatcher=DjangoEventDispatcher(),
    )


def get_query_handlers():
    return EventQueryHandlers(
        event_repo=DjangoEventRepository(),
        checklist_repo=DjangoChecklistRepository(),
        checklist_item_repo=DjangoChecklistItemRepository(),
        budget_repo=DjangoBudgetLineRepository(),
        guest_repo=DjangoGuestEntryRepository(),
        timeline_repo=DjangoTimelineBlockRepository(),
    )