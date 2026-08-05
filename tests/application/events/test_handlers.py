import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock, call

import pytest

from application.events.commands import (
    AddBudgetLineCommand,
    AddChecklistItemCommand,
    AddGuestCommand,
    AddTimelineBlockCommand,
    CreateChecklistCommand,
    CreateEventCommand,
    DeleteEventCommand,
    UpdateBudgetLineCommand,
    UpdateChecklistItemCommand,
    UpdateEventCommand,
    UpdateGuestCommand,
)
from application.events.handlers import EventCommandHandlers
from domain.events.entities import (
    BudgetCategory,
    BudgetLine,
    Checklist,
    ChecklistItem,
    ChecklistItemStatus,
    DietaryRestriction,
    Event,
    EventType,
    GuestEntry,
    RSVPStatus,
    TimelineBlock,
)
from domain.events.events import (
    BudgetLineAdded,
    ChecklistCreated,
    EventCreated,
    GuestAdded,
    TimelineBlockAdded,
)


@pytest.fixture
def repos():
    return {
        "event": Mock(name="event_repo"),
        "checklist": Mock(name="checklist_repo"),
        "item": Mock(name="checklist_item_repo"),
        "budget": Mock(name="budget_repo"),
        "guest": Mock(name="guest_repo"),
        "timeline": Mock(name="timeline_repo"),
        "dispatcher": Mock(name="event_dispatcher"),
    }


@pytest.fixture
def handlers(repos):
    return EventCommandHandlers(
        repos["event"],
        repos["checklist"],
        repos["item"],
        repos["budget"],
        repos["guest"],
        repos["timeline"],
        repos["dispatcher"],
    )


def _echo_saved(repo):
    repo.save.side_effect = lambda entity: entity


def _event(event_id=None) -> Event:
    return Event(
        id=event_id or uuid.uuid4(),
        planner_id=uuid.uuid4(),
        name="Original Event",
        event_type=EventType.CORPORATE,
        event_date=date(2026, 5, 1),
        venue="Original Venue",
        expected_guests=50,
        total_budget=1000.0,
    )


def _checklist(checklist_id=None) -> Checklist:
    return Checklist(
        id=checklist_id or uuid.uuid4(),
        event_id=uuid.uuid4(),
        name="Planning",
    )


def _item(item_id=None, *, checklist_id=None, order=0) -> ChecklistItem:
    return ChecklistItem(
        id=item_id or uuid.uuid4(),
        checklist_id=checklist_id or uuid.uuid4(),
        description="Book venue",
        status=ChecklistItemStatus.PENDING,
        due_date=date(2026, 4, 1),
        assigned_to="Planner",
        order=order,
    )


def _budget_line(line_id=None) -> BudgetLine:
    return BudgetLine(
        id=line_id or uuid.uuid4(),
        event_id=uuid.uuid4(),
        category=BudgetCategory.VENUE,
        description="Venue",
        estimated_cost=1000.0,
        actual_cost=None,
        notes="Initial",
    )


def _guest(guest_id=None) -> GuestEntry:
    return GuestEntry(
        id=guest_id or uuid.uuid4(),
        event_id=uuid.uuid4(),
        full_name="Guest One",
        email="guest@example.com",
        phone="+250788000000",
        rsvp_status=RSVPStatus.PENDING,
        dietary_restrictions=[DietaryRestriction.NONE],
        plus_one=False,
        table_assignment=None,
        notes="Initial",
    )


def _timeline_block(block_id=None, *, event_id=None, order=0) -> TimelineBlock:
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    return TimelineBlock(
        id=block_id or uuid.uuid4(),
        event_id=event_id or uuid.uuid4(),
        title="Ceremony",
        start_time=start,
        end_time=start + timedelta(hours=1),
        description="Main ceremony",
        location="Hall",
        order=order,
    )


def test_create_event_saves_new_event_and_dispatches_event_created(handlers, repos):
    _echo_saved(repos["event"])
    planner_id = uuid.uuid4()

    result = handlers.create_event(
        CreateEventCommand(
            planner_id=planner_id,
            name="Launch",
            event_type="corporate",
            event_date=date(2026, 6, 1),
            venue="Convention Center",
            expected_guests=120,
            total_budget=5000.0,
        )
    )

    saved_event = repos["event"].save.call_args.args[0]
    assert repos["event"].method_calls == [call.save(saved_event)]
    assert saved_event.planner_id == planner_id
    assert saved_event.name == "Launch"
    assert saved_event.event_type == EventType.CORPORATE
    assert saved_event.event_date == date(2026, 6, 1)
    assert saved_event.venue == "Convention Center"
    assert saved_event.expected_guests == 120
    assert saved_event.total_budget == 5000.0
    assert result.id == saved_event.id
    assert result.event_type == "corporate"

    dispatched = repos["dispatcher"].dispatch.call_args.args[0]
    assert repos["dispatcher"].method_calls == [call.dispatch(dispatched)]
    assert isinstance(dispatched, EventCreated)
    assert dispatched.event_id == saved_event.id
    assert dispatched.planner_id == planner_id


def test_update_event_loads_saves_mutated_event_and_dispatches_no_event(handlers, repos):
    event_id = uuid.uuid4()
    loaded = _event(event_id)
    repos["event"].get_by_id.return_value = loaded
    _echo_saved(repos["event"])

    result = handlers.update_event(
        UpdateEventCommand(
            event_id=event_id,
            name="Updated",
            event_type="wedding",
            event_date=date(2026, 7, 2),
            venue="New Venue",
            expected_guests=80,
            total_budget=7000.0,
        )
    )

    assert repos["event"].method_calls == [call.get_by_id(event_id), call.save(loaded)]
    assert loaded.name == "Updated"
    assert loaded.event_type == EventType.WEDDING
    assert loaded.event_date == date(2026, 7, 2)
    assert loaded.venue == "New Venue"
    assert loaded.expected_guests == 80
    assert loaded.total_budget == 7000.0
    assert result.name == "Updated"
    repos["dispatcher"].dispatch.assert_not_called()


def test_update_event_raises_without_save_or_dispatch_when_missing(handlers, repos):
    event_id = uuid.uuid4()
    repos["event"].get_by_id.return_value = None

    with pytest.raises(ValueError, match="Event not found"):
        handlers.update_event(UpdateEventCommand(event_id=event_id, name="Updated"))

    assert repos["event"].method_calls == [call.get_by_id(event_id)]
    repos["dispatcher"].dispatch.assert_not_called()


def test_delete_event_calls_repository_delete_only(handlers, repos):
    event_id = uuid.uuid4()

    result = handlers.delete_event(DeleteEventCommand(event_id=event_id))

    assert result is None
    assert repos["event"].method_calls == [call.delete(event_id)]
    repos["dispatcher"].dispatch.assert_not_called()


def test_create_checklist_saves_new_checklist_and_dispatches_checklist_created(handlers, repos):
    _echo_saved(repos["checklist"])
    event_id = uuid.uuid4()

    result = handlers.create_checklist(CreateChecklistCommand(event_id=event_id, name="Setup"))

    saved = repos["checklist"].save.call_args.args[0]
    assert repos["checklist"].method_calls == [call.save(saved)]
    assert saved.event_id == event_id
    assert saved.name == "Setup"
    assert result.id == saved.id
    assert result.name == "Setup"

    dispatched = repos["dispatcher"].dispatch.call_args.args[0]
    assert repos["dispatcher"].method_calls == [call.dispatch(dispatched)]
    assert isinstance(dispatched, ChecklistCreated)
    assert dispatched.checklist_id == saved.id
    assert dispatched.event_id == event_id


def test_add_checklist_item_lists_existing_items_saves_next_order_and_dispatches_no_event(handlers, repos):
    checklist_id = uuid.uuid4()
    existing = [_item(checklist_id=checklist_id, order=0), _item(checklist_id=checklist_id, order=4)]
    repos["item"].list_by_checklist.return_value = existing
    _echo_saved(repos["item"])

    result = handlers.add_checklist_item(
        AddChecklistItemCommand(
            checklist_id=checklist_id,
            description="Send invites",
            due_date=date(2026, 4, 20),
            assigned_to="Aline",
        )
    )

    saved = repos["item"].save.call_args.args[0]
    assert repos["item"].method_calls == [call.list_by_checklist(checklist_id), call.save(saved)]
    assert saved.checklist_id == checklist_id
    assert saved.description == "Send invites"
    assert saved.due_date == date(2026, 4, 20)
    assert saved.assigned_to == "Aline"
    assert saved.order == 5
    assert result.order == 5
    repos["dispatcher"].dispatch.assert_not_called()


def test_update_checklist_item_loads_saves_mutated_item_and_dispatches_no_event(handlers, repos):
    item_id = uuid.uuid4()
    loaded = _item(item_id)
    repos["item"].get_by_id.return_value = loaded
    _echo_saved(repos["item"])

    result = handlers.update_checklist_item(
        UpdateChecklistItemCommand(
            item_id=item_id,
            description="Confirm venue",
            status="in_progress",
            due_date=date(2026, 4, 30),
            assigned_to="Jean",
        )
    )

    assert repos["item"].method_calls == [call.get_by_id(item_id), call.save(loaded)]
    assert loaded.description == "Confirm venue"
    assert loaded.status == ChecklistItemStatus.IN_PROGRESS
    assert loaded.due_date == date(2026, 4, 30)
    assert loaded.assigned_to == "Jean"
    assert result.status == "in_progress"
    repos["dispatcher"].dispatch.assert_not_called()


def test_update_checklist_item_raises_without_save_or_dispatch_when_missing(handlers, repos):
    item_id = uuid.uuid4()
    repos["item"].get_by_id.return_value = None

    with pytest.raises(ValueError, match="Checklist item not found"):
        handlers.update_checklist_item(UpdateChecklistItemCommand(item_id=item_id, status="completed"))

    assert repos["item"].method_calls == [call.get_by_id(item_id)]
    repos["dispatcher"].dispatch.assert_not_called()


def test_add_budget_line_saves_new_line_and_dispatches_budget_line_added(handlers, repos):
    _echo_saved(repos["budget"])
    event_id = uuid.uuid4()

    result = handlers.add_budget_line(
        AddBudgetLineCommand(
            event_id=event_id,
            category="catering",
            description="Dinner",
            estimated_cost=3000.0,
            actual_cost=3200.0,
            notes="Updated quote",
        )
    )

    saved = repos["budget"].save.call_args.args[0]
    assert repos["budget"].method_calls == [call.save(saved)]
    assert saved.event_id == event_id
    assert saved.category == BudgetCategory.CATERING
    assert saved.description == "Dinner"
    assert saved.estimated_cost == 3000.0
    assert saved.actual_cost == 3200.0
    assert saved.notes == "Updated quote"
    assert result.category == "catering"

    dispatched = repos["dispatcher"].dispatch.call_args.args[0]
    assert repos["dispatcher"].method_calls == [call.dispatch(dispatched)]
    assert isinstance(dispatched, BudgetLineAdded)
    assert dispatched.budget_line_id == saved.id
    assert dispatched.event_id == event_id


def test_update_budget_line_loads_saves_mutated_line_and_dispatches_no_event(handlers, repos):
    line_id = uuid.uuid4()
    loaded = _budget_line(line_id)
    repos["budget"].get_by_id.return_value = loaded
    _echo_saved(repos["budget"])

    result = handlers.update_budget_line(
        UpdateBudgetLineCommand(
            line_id=line_id,
            estimated_cost=1500.0,
            actual_cost=1400.0,
            notes="Paid",
        )
    )

    assert repos["budget"].method_calls == [call.get_by_id(line_id), call.save(loaded)]
    assert loaded.estimated_cost == 1500.0
    assert loaded.actual_cost == 1400.0
    assert loaded.notes == "Paid"
    assert result.actual_cost == 1400.0
    repos["dispatcher"].dispatch.assert_not_called()


def test_update_budget_line_raises_without_save_or_dispatch_when_missing(handlers, repos):
    line_id = uuid.uuid4()
    repos["budget"].get_by_id.return_value = None

    with pytest.raises(ValueError, match="Budget line not found"):
        handlers.update_budget_line(UpdateBudgetLineCommand(line_id=line_id, actual_cost=100.0))

    assert repos["budget"].method_calls == [call.get_by_id(line_id)]
    repos["dispatcher"].dispatch.assert_not_called()


def test_add_guest_saves_new_guest_and_dispatches_guest_added(handlers, repos):
    _echo_saved(repos["guest"])
    event_id = uuid.uuid4()

    result = handlers.add_guest(
        AddGuestCommand(
            event_id=event_id,
            full_name="Guest Two",
            email="guest2@example.com",
            phone="+250788111222",
            dietary_restrictions=["vegan", "halal"],
            plus_one=True,
            notes="VIP",
        )
    )

    saved = repos["guest"].save.call_args.args[0]
    assert repos["guest"].method_calls == [call.save(saved)]
    assert saved.event_id == event_id
    assert saved.full_name == "Guest Two"
    assert saved.email == "guest2@example.com"
    assert saved.phone == "+250788111222"
    assert saved.dietary_restrictions == [DietaryRestriction.VEGAN, DietaryRestriction.HALAL]
    assert saved.plus_one is True
    assert saved.notes == "VIP"
    assert result.dietary_restrictions == ["vegan", "halal"]

    dispatched = repos["dispatcher"].dispatch.call_args.args[0]
    assert repos["dispatcher"].method_calls == [call.dispatch(dispatched)]
    assert isinstance(dispatched, GuestAdded)
    assert dispatched.guest_id == saved.id
    assert dispatched.event_id == event_id


def test_update_guest_loads_saves_mutated_guest_and_dispatches_no_event(handlers, repos):
    guest_id = uuid.uuid4()
    loaded = _guest(guest_id)
    repos["guest"].get_by_id.return_value = loaded
    _echo_saved(repos["guest"])

    result = handlers.update_guest(
        UpdateGuestCommand(
            guest_id=guest_id,
            full_name="Updated Guest",
            email="updated@example.com",
            phone="+250788333444",
            rsvp_status="accepted",
            dietary_restrictions=["vegetarian"],
            plus_one=True,
            table_assignment="Table 3",
            notes="Window seat",
        )
    )

    assert repos["guest"].method_calls == [call.get_by_id(guest_id), call.save(loaded)]
    assert loaded.full_name == "Updated Guest"
    assert loaded.email == "updated@example.com"
    assert loaded.phone == "+250788333444"
    assert loaded.rsvp_status == RSVPStatus.ACCEPTED
    assert loaded.dietary_restrictions == [DietaryRestriction.VEGETARIAN]
    assert loaded.plus_one is True
    assert loaded.table_assignment == "Table 3"
    assert loaded.notes == "Window seat"
    assert result.rsvp_status == "accepted"
    repos["dispatcher"].dispatch.assert_not_called()


def test_update_guest_raises_without_save_or_dispatch_when_missing(handlers, repos):
    guest_id = uuid.uuid4()
    repos["guest"].get_by_id.return_value = None

    with pytest.raises(ValueError, match="Guest not found"):
        handlers.update_guest(UpdateGuestCommand(guest_id=guest_id, full_name="Updated"))

    assert repos["guest"].method_calls == [call.get_by_id(guest_id)]
    repos["dispatcher"].dispatch.assert_not_called()


def test_add_timeline_block_lists_existing_blocks_saves_next_order_and_dispatches_timeline_block_added(
    handlers,
    repos,
):
    event_id = uuid.uuid4()
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    existing = [_timeline_block(event_id=event_id, order=1), _timeline_block(event_id=event_id, order=7)]
    repos["timeline"].list_by_event.return_value = existing
    _echo_saved(repos["timeline"])

    result = handlers.add_timeline_block(
        AddTimelineBlockCommand(
            event_id=event_id,
            title="Reception",
            start_time=start,
            end_time=start + timedelta(hours=2),
            description="Dinner and speeches",
            location="Garden",
        )
    )

    saved = repos["timeline"].save.call_args.args[0]
    assert repos["timeline"].method_calls == [call.list_by_event(event_id), call.save(saved)]
    assert saved.event_id == event_id
    assert saved.title == "Reception"
    assert saved.start_time == start
    assert saved.end_time == start + timedelta(hours=2)
    assert saved.description == "Dinner and speeches"
    assert saved.location == "Garden"
    assert saved.order == 8
    assert result.order == 8

    dispatched = repos["dispatcher"].dispatch.call_args.args[0]
    assert repos["dispatcher"].method_calls == [call.dispatch(dispatched)]
    assert isinstance(dispatched, TimelineBlockAdded)
    assert dispatched.block_id == saved.id
    assert dispatched.event_id == event_id
