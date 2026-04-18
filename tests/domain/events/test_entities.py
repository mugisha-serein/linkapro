import uuid
from datetime import date, datetime, timezone
from freezegun import freeze_time

from domain.events.entities import Event, EventType, ChecklistItem, ChecklistItemStatus
from domain.shared.utils import utc_now


class TestEvent:
    def test_create_event(self):
        event = Event(
            id=uuid.uuid4(),
            planner_id=uuid.uuid4(),
            name="Wedding",
            event_type=EventType.WEDDING,
            event_date=date(2025, 6, 15),
        )
        assert event.expected_guests == 0

    def test_update_details(self):
        event = Event(
            id=uuid.uuid4(),
            planner_id=uuid.uuid4(),
            name="Old",
            event_type=EventType.CORPORATE,
            event_date=date(2025, 1, 1),
        )
        frozen_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        with freeze_time(frozen_time):
            event.update_details(name="New Name", expected_guests=100)
        assert event.name == "New Name"
        assert event.expected_guests == 100
        assert event.updated_at == frozen_time


class TestChecklistItem:
    def test_mark_completed(self):
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=uuid.uuid4(),
            description="Do something",
            status=ChecklistItemStatus.PENDING,
        )
        frozen_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with freeze_time(frozen_time):
            item.mark_completed()
        assert item.status == ChecklistItemStatus.COMPLETED
        assert item.updated_at == frozen_time