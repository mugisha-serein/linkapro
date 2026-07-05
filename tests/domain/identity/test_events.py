import uuid
from dataclasses import fields
from datetime import datetime, UTC

from domain.identity.entities import UserRole
from domain.identity.events import (
    UserDeactivated,
    UserLoggedIn,
    UserOAuthLinked,
    UserPasswordChanged,
    UserRegistered,
)
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

    def test_events_do_not_define_secret_fields(self):
        forbidden_names = {
            "access_token",
            "refresh_token",
            "password",
            "password_hash",
            "plain_password",
            "totp_secret",
            "secret",
            "token",
        }
        event_types = [
            UserRegistered,
            UserLoggedIn,
            UserPasswordChanged,
            UserOAuthLinked,
            UserDeactivated,
        ]

        for event_type in event_types:
            event_field_names = {field.name for field in fields(event_type)}
            assert event_field_names.isdisjoint(forbidden_names)
