import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from domain.events.entities import (
    BudgetCategory,
    BudgetLine,
    Checklist,
    ChecklistItem,
    ChecklistItemStatus,
    Event,
    EventType,
    GuestEntry,
    RSVPStatus,
    TimelineBlock,
)


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

    def test_update_details_updates_all_non_none_fields_and_preserves_omitted_fields(self):
        original_date = date(2025, 1, 1)
        event = Event(
            id=uuid.uuid4(),
            planner_id=uuid.uuid4(),
            name="Old",
            event_type=EventType.CORPORATE,
            event_date=original_date,
            venue="Old Venue",
            expected_guests=20,
            total_budget=1000.0,
        )
        frozen_time = datetime(2025, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            event.update_details(
                name="New",
                event_type=EventType.WEDDING,
                venue="New Venue",
                expected_guests=75,
            )

        assert event.name == "New"
        assert event.event_type == EventType.WEDDING
        assert event.event_date == original_date
        assert event.venue == "New Venue"
        assert event.expected_guests == 75
        assert event.total_budget == 1000.0
        assert event.updated_at == frozen_time

    def test_update_details_currently_accepts_blank_name_and_negative_numbers(self):
        event = Event(
            id=uuid.uuid4(),
            planner_id=uuid.uuid4(),
            name="Original",
            event_type=EventType.OTHER,
            event_date=date(2025, 3, 1),
            expected_guests=10,
            total_budget=500.0,
        )
        frozen_time = datetime(2025, 3, 1, 8, 30, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            event.update_details(name="", expected_guests=-5, total_budget=-1.25)

        assert event.name == ""
        assert event.expected_guests == -5
        assert event.total_budget == -1.25
        assert event.updated_at == frozen_time


class TestChecklist:
    def test_rename_sets_name_and_updated_at(self):
        checklist = Checklist(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            name="Before",
        )
        frozen_time = datetime(2025, 4, 1, 10, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            checklist.rename("After")

        assert checklist.name == "After"
        assert checklist.updated_at == frozen_time

    def test_rename_currently_accepts_blank_name(self):
        checklist = Checklist(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            name="Before",
        )

        checklist.rename("")

        assert checklist.name == ""


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

    def test_mark_in_progress_sets_status_and_updated_at(self):
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=uuid.uuid4(),
            description="Do something",
            status=ChecklistItemStatus.PENDING,
        )
        frozen_time = datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            item.mark_in_progress()

        assert item.status == ChecklistItemStatus.IN_PROGRESS
        assert item.updated_at == frozen_time

    def test_mark_in_progress_currently_allows_completed_item_to_move_backwards(self):
        item = ChecklistItem(
            id=uuid.uuid4(),
            checklist_id=uuid.uuid4(),
            description="Do something",
            status=ChecklistItemStatus.COMPLETED,
        )

        item.mark_in_progress()

        assert item.status == ChecklistItemStatus.IN_PROGRESS


class TestBudgetLine:
    def test_set_actual_cost_sets_amount_and_updated_at(self):
        line = BudgetLine(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            category=BudgetCategory.VENUE,
            description="Venue",
            estimated_cost=1000.0,
        )
        frozen_time = datetime(2025, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            line.set_actual_cost(1200.5)

        assert line.actual_cost == 1200.5
        assert line.updated_at == frozen_time

    def test_set_actual_cost_currently_accepts_negative_amount(self):
        line = BudgetLine(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            category=BudgetCategory.OTHER,
            description="Adjustment",
            estimated_cost=-10.0,
        )

        line.set_actual_cost(-25.75)

        assert line.estimated_cost == -10.0
        assert line.actual_cost == -25.75


class TestGuestEntry:
    def test_update_rsvp_sets_status_and_updated_at(self):
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            full_name="Guest One",
        )
        frozen_time = datetime(2025, 7, 1, 11, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            guest.update_rsvp(RSVPStatus.ACCEPTED)

        assert guest.rsvp_status == RSVPStatus.ACCEPTED
        assert guest.updated_at == frozen_time

    def test_update_rsvp_currently_accepts_raw_status_values(self):
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            full_name="Guest One",
        )

        guest.update_rsvp("unknown")

        assert guest.rsvp_status == "unknown"

    def test_assign_table_sets_table_and_updated_at(self):
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            full_name="Guest One",
        )
        frozen_time = datetime(2025, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            guest.assign_table("Table 4")

        assert guest.table_assignment == "Table 4"
        assert guest.updated_at == frozen_time

    def test_assign_table_currently_accepts_blank_table_name(self):
        guest = GuestEntry(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            full_name="Guest One",
            table_assignment="Table 1",
        )

        guest.assign_table("")

        assert guest.table_assignment == ""


class TestTimelineBlock:
    def test_reschedule_sets_start_end_and_updated_at(self):
        start = datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        block = TimelineBlock(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            title="Ceremony",
            start_time=start,
            end_time=end,
        )
        new_start = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
        new_end = new_start + timedelta(minutes=45)
        frozen_time = datetime(2025, 8, 1, 9, 0, 0, tzinfo=timezone.utc)

        with freeze_time(frozen_time):
            block.reschedule(new_start, new_end)

        assert block.start_time == new_start
        assert block.end_time == new_end
        assert block.updated_at == frozen_time

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (
                datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
            (
                datetime(2025, 8, 1, 11, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    def test_reschedule_rejects_equal_or_reversed_times_without_changing_block(self, start, end):
        original_start = datetime(2025, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
        original_end = datetime(2025, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        original_updated_at = datetime(2025, 8, 1, 7, 30, 0, tzinfo=timezone.utc)
        block = TimelineBlock(
            id=uuid.uuid4(),
            event_id=uuid.uuid4(),
            title="Ceremony",
            start_time=original_start,
            end_time=original_end,
            updated_at=original_updated_at,
        )

        with pytest.raises(ValueError, match="End time must be after start time"):
            block.reschedule(start, end)

        assert block.start_time == original_start
        assert block.end_time == original_end
        assert block.updated_at == original_updated_at
