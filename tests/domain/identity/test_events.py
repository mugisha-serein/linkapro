import uuid
from datetime import datetime, UTC

from domain.identity.entities import UserRole
from domain.identity.events import UserRegistered
from domain.identity.value_objects import Email


class TestIdentityEvents:
    def test_events_have_generated_event_id(self):
        event = UserRegistered(
            user_id=uuid.uuid4(),
            email=Email("user@example.com"),
            role=UserRole.PLANNER,
            occurred_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert isinstance(event.event_id, uuid.UUID)
