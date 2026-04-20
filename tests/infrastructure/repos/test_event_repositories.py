import uuid
from datetime import date, datetime, timezone
import pytest

from domain.events.entities import (
    Event, Checklist, ChecklistItem, BudgetLine, GuestEntry, TimelineBlock,
    EventType, ChecklistItemStatus, BudgetCategory, RSVPStatus, DietaryRestriction
)
from infrastructure.repos.django_event_repository import DjangoEventRepository
from infrastructure.repos.django_checklist_repository import DjangoChecklistRepository
from infrastructure.repos.django_checklist_item_repository import DjangoChecklistItemRepository
from infrastructure.repos.django_budget_line_repository import DjangoBudgetLineRepository
from infrastructure.repos.django_guest_entry_repository import DjangoGuestEntryRepository
from infrastructure.repos.django_timeline_block_repository import DjangoTimelineBlockRepository
from django_app.identity.models import User
from django_app.events.models import Event as DjangoEvent

pytestmark = pytest.mark.django_db


class TestDjangoEventRepository:
    def test_save_and_retrieve(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        repo = DjangoEventRepository()
        event = Event(
            id=uuid.uuid4(),
            planner_id=user.id,
            name="Wedding",
            event_type=EventType.WEDDING,
            event_date=date(2025, 6, 15),
            venue="Beach Resort",
            expected_guests=100,
            total_budget=5000.0,
        )
        saved = repo.save(event)
        assert saved.id == event.id
        assert DjangoEvent.objects.count() == 1

        retrieved = repo.get_by_id(event.id)
        assert retrieved is not None
        assert retrieved.name == "Wedding"
        assert retrieved.venue == "Beach Resort"

    def test_list_by_planner(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        other_user = User.objects.create_user(email="other@test.com", password="p", role="planner")
        repo = DjangoEventRepository()
        repo.save(Event(
            id=uuid.uuid4(), planner_id=user.id, name="Event1",
            event_type=EventType.CORPORATE, event_date=date(2025, 1, 1)
        ))
        repo.save(Event(
            id=uuid.uuid4(), planner_id=user.id, name="Event2",
            event_type=EventType.TRAVEL, event_date=date(2025, 2, 1)
        ))
        repo.save(Event(
            id=uuid.uuid4(), planner_id=other_user.id, name="OtherEvent",
            event_type=EventType.WEDDING, event_date=date(2025, 3, 1)
        ))
        events = repo.list_by_planner(user.id)
        assert len(events) == 2
        names = {e.name for e in events}
        assert names == {"Event1", "Event2"}

    def test_update_existing(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        repo = DjangoEventRepository()
        event = Event(
            id=uuid.uuid4(), planner_id=user.id, name="Old Name",
            event_type=EventType.CORPORATE, event_date=date(2025, 1, 1)
        )
        repo.save(event)
        event.name = "New Name"
        event.expected_guests = 150
        repo.save(event)
        updated = repo.get_by_id(event.id)
        assert updated.name == "New Name"
        assert updated.expected_guests == 150

    def test_delete(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        repo = DjangoEventRepository()
        event = Event(
            id=uuid.uuid4(), planner_id=user.id, name="Delete Me",
            event_type=EventType.OTHER, event_date=date(2025, 1, 1)
        )
        repo.save(event)
        assert repo.get_by_id(event.id) is not None
        repo.delete(event.id)
        assert repo.get_by_id(event.id) is None


class TestDjangoChecklistRepository:
    def test_save_and_list_by_event(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoChecklistRepository()
        checklist = Checklist(
            id=uuid.uuid4(),
            event_id=event.id,
            name="To Do",
        )
        saved = repo.save(checklist)
        assert saved.name == "To Do"
        checklists = repo.list_by_event(event.id)
        assert len(checklists) == 1
        assert checklists[0].name == "To Do"

    def test_delete(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoChecklistRepository()
        checklist = Checklist(id=uuid.uuid4(), event_id=event.id, name="To Do")
        repo.save(checklist)
        repo.delete(checklist.id)
        assert repo.get_by_id(checklist.id) is None


class TestDjangoChecklistItemRepository:
    def test_save_and_list_by_checklist(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        from django_app.events.models import Checklist as DjangoChecklist
        checklist = DjangoChecklist.objects.create(event=event, name="Checklist")
        repo = DjangoChecklistItemRepository()
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=checklist.id,
            description="Book venue",
            status=ChecklistItemStatus.PENDING,
            due_date=date(2025, 5, 1),
            assigned_to="Planner",
            order=0,
        )
        saved = repo.save(item)
        assert saved.description == "Book venue"
        items = repo.list_by_checklist(checklist.id)
        assert len(items) == 1
        assert items[0].assigned_to == "Planner"

    def test_order_preserved(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        from django_app.events.models import Checklist as DjangoChecklist
        checklist = DjangoChecklist.objects.create(event=event, name="Checklist")
        repo = DjangoChecklistItemRepository()
        repo.save(ChecklistItem(id=uuid.uuid4(), checklist_id=checklist.id, description="First", order=0))
        repo.save(ChecklistItem(id=uuid.uuid4(), checklist_id=checklist.id, description="Second", order=1))
        items = repo.list_by_checklist(checklist.id)
        assert items[0].description == "First"
        assert items[1].description == "Second"


class TestDjangoBudgetLineRepository:
    def test_crud(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoBudgetLineRepository()
        line = BudgetLine(
            id=uuid.uuid4(),
            event_id=event.id,
            category=BudgetCategory.CATERING,
            description="Dinner",
            estimated_cost=2000.0,
            actual_cost=1800.0,
            notes="Buffet",
        )
        saved = repo.save(line)
        assert saved.category == BudgetCategory.CATERING
        lines = repo.list_by_event(event.id)
        assert len(lines) == 1
        assert lines[0].estimated_cost == 2000.0
        repo.delete(saved.id)
        assert repo.get_by_id(saved.id) is None


class TestDjangoGuestEntryRepository:
    def test_save_and_list(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoGuestEntryRepository()
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=event.id,
            full_name="John Doe",
            email="john@example.com",
            phone="123",
            rsvp_status=RSVPStatus.ACCEPTED,
            dietary_restrictions=[DietaryRestriction.VEGETARIAN],
            plus_one=True,
            table_assignment="Table 5",
            notes="Allergic to nuts",
        )
        saved = repo.save(guest)
        guests = repo.list_by_event(event.id)
        assert len(guests) == 1
        assert guests[0].full_name == "John Doe"
        assert guests[0].dietary_restrictions == [DietaryRestriction.VEGETARIAN]


class TestDjangoTimelineBlockRepository:
    def test_save_and_list_by_event(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoTimelineBlockRepository()
        start = datetime(2025, 6, 15, 14, 0, tzinfo=timezone.utc)
        end = datetime(2025, 6, 15, 15, 0, tzinfo=timezone.utc)
        block = TimelineBlock(
            id=uuid.uuid4(),
            event_id=event.id,
            title="Ceremony",
            start_time=start,
            end_time=end,
            description="Main ceremony",
            location="Chapel",
            order=0,
        )
        saved = repo.save(block)
        blocks = repo.list_by_event(event.id)
        assert len(blocks) == 1
        assert blocks[0].title == "Ceremony"

    def test_order_preserved(self):
        user = User.objects.create_user(email="planner@test.com", password="p", role="planner")
        event = DjangoEvent.objects.create(
            planner=user, name="Event", event_type="wedding", event_date="2025-01-01"
        )
        repo = DjangoTimelineBlockRepository()
        start1 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        end1 = datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc)
        start2 = datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc)
        end2 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        repo.save(TimelineBlock(
            id=uuid.uuid4(), event_id=event.id, title="First",
            start_time=start1, end_time=end1, order=0
        ))
        repo.save(TimelineBlock(
            id=uuid.uuid4(), event_id=event.id, title="Second",
            start_time=start2, end_time=end2, order=1
        ))
        blocks = repo.list_by_event(event.id)
        assert blocks[0].title == "First"
        assert blocks[1].title == "Second"