import inspect
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, get_type_hints
from unittest.mock import call, create_autospec

import pytest

from domain.events.entities import (
    BudgetCategory,
    BudgetLine,
    Checklist,
    ChecklistItem,
    Event,
    EventType,
    GuestEntry,
    TimelineBlock,
)
from domain.events.interfaces import (
    IBudgetLineRepository,
    IChecklistItemRepository,
    IChecklistRepository,
    IEventRepository,
    IGuestEntryRepository,
    ITimelineBlockRepository,
)


@dataclass(frozen=True)
class RepositoryContract:
    repository: type
    methods: dict[str, tuple[list[tuple[str, object]], object]]
    calls: list[tuple[str, tuple[object, ...]]]


def _event() -> Event:
    return Event(
        id=uuid.uuid4(),
        planner_id=uuid.uuid4(),
        name="Wedding",
        event_type=EventType.WEDDING,
        event_date=date(2026, 5, 1),
    )


def _checklist() -> Checklist:
    return Checklist(id=uuid.uuid4(), event_id=uuid.uuid4(), name="Planning")


def _checklist_item() -> ChecklistItem:
    return ChecklistItem(id=uuid.uuid4(), checklist_id=uuid.uuid4(), description="Book venue")


def _budget_line() -> BudgetLine:
    return BudgetLine(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        category=BudgetCategory.VENUE,
        description="Venue",
        estimated_cost=1000.0,
    )


def _guest() -> GuestEntry:
    return GuestEntry(id=uuid.uuid4(), event_id=uuid.uuid4(), full_name="Guest One")


def _timeline_block() -> TimelineBlock:
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    return TimelineBlock(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        title="Ceremony",
        start_time=start,
        end_time=start + timedelta(hours=1),
    )


EVENT_ID = uuid.uuid4()
PLANNER_ID = uuid.uuid4()
CHECKLIST_ID = uuid.uuid4()
ITEM_ID = uuid.uuid4()
BUDGET_LINE_ID = uuid.uuid4()
GUEST_ID = uuid.uuid4()
TIMELINE_BLOCK_ID = uuid.uuid4()

CONTRACTS = [
    RepositoryContract(
        repository=IEventRepository,
        methods={
            "get_by_id": ([("event_id", uuid.UUID)], Optional[Event]),
            "list_by_planner": ([("planner_id", uuid.UUID)], List[Event]),
            "save": ([("event", Event)], Event),
            "delete": ([("event_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (EVENT_ID,)),
            ("list_by_planner", (PLANNER_ID,)),
            ("save", (_event(),)),
            ("delete", (EVENT_ID,)),
        ],
    ),
    RepositoryContract(
        repository=IChecklistRepository,
        methods={
            "get_by_id": ([("checklist_id", uuid.UUID)], Optional[Checklist]),
            "list_by_event": ([("event_id", uuid.UUID)], List[Checklist]),
            "save": ([("checklist", Checklist)], Checklist),
            "delete": ([("checklist_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (CHECKLIST_ID,)),
            ("list_by_event", (EVENT_ID,)),
            ("save", (_checklist(),)),
            ("delete", (CHECKLIST_ID,)),
        ],
    ),
    RepositoryContract(
        repository=IChecklistItemRepository,
        methods={
            "get_by_id": ([("item_id", uuid.UUID)], Optional[ChecklistItem]),
            "list_by_checklist": ([("checklist_id", uuid.UUID)], List[ChecklistItem]),
            "save": ([("item", ChecklistItem)], ChecklistItem),
            "delete": ([("item_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (ITEM_ID,)),
            ("list_by_checklist", (CHECKLIST_ID,)),
            ("save", (_checklist_item(),)),
            ("delete", (ITEM_ID,)),
        ],
    ),
    RepositoryContract(
        repository=IBudgetLineRepository,
        methods={
            "get_by_id": ([("line_id", uuid.UUID)], Optional[BudgetLine]),
            "list_by_event": ([("event_id", uuid.UUID)], List[BudgetLine]),
            "save": ([("line", BudgetLine)], BudgetLine),
            "delete": ([("line_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (BUDGET_LINE_ID,)),
            ("list_by_event", (EVENT_ID,)),
            ("save", (_budget_line(),)),
            ("delete", (BUDGET_LINE_ID,)),
        ],
    ),
    RepositoryContract(
        repository=IGuestEntryRepository,
        methods={
            "get_by_id": ([("guest_id", uuid.UUID)], Optional[GuestEntry]),
            "list_by_event": ([("event_id", uuid.UUID)], List[GuestEntry]),
            "save": ([("guest", GuestEntry)], GuestEntry),
            "delete": ([("guest_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (GUEST_ID,)),
            ("list_by_event", (EVENT_ID,)),
            ("save", (_guest(),)),
            ("delete", (GUEST_ID,)),
        ],
    ),
    RepositoryContract(
        repository=ITimelineBlockRepository,
        methods={
            "get_by_id": ([("block_id", uuid.UUID)], Optional[TimelineBlock]),
            "list_by_event": ([("event_id", uuid.UUID)], List[TimelineBlock]),
            "save": ([("block", TimelineBlock)], TimelineBlock),
            "delete": ([("block_id", uuid.UUID)], type(None)),
        },
        calls=[
            ("get_by_id", (TIMELINE_BLOCK_ID,)),
            ("list_by_event", (EVENT_ID,)),
            ("save", (_timeline_block(),)),
            ("delete", (TIMELINE_BLOCK_ID,)),
        ],
    ),
]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda contract: contract.repository.__name__)
def test_event_repository_interface_method_signatures_are_current_contract(contract):
    assert contract.repository.__abstractmethods__ == frozenset(contract.methods)

    for method_name, (expected_params, expected_return) in contract.methods.items():
        method = getattr(contract.repository, method_name)
        signature = inspect.signature(method)
        hints = get_type_hints(method)

        assert tuple(signature.parameters) == ("self", *(name for name, _ in expected_params))
        for name, expected_type in expected_params:
            assert hints[name] is expected_type
        assert hints["return"] == expected_return


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda contract: contract.repository.__name__)
def test_event_repository_autospec_mocks_accept_current_call_shapes(contract):
    repo = create_autospec(contract.repository, instance=True, spec_set=True)

    for method_name, args in contract.calls:
        getattr(repo, method_name)(*args)

    assert repo.method_calls == [call.__getattr__(method_name)(*args) for method_name, args in contract.calls]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda contract: contract.repository.__name__)
def test_event_repository_autospec_mocks_reject_unknown_methods_and_missing_required_args(contract):
    repo = create_autospec(contract.repository, instance=True, spec_set=True)
    first_method = next(iter(contract.methods))

    with pytest.raises(AttributeError):
        repo.not_a_repository_method

    with pytest.raises(TypeError):
        getattr(repo, first_method)()
