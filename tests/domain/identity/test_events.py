import uuid
import pytest
from dataclasses import fields
from datetime import datetime, UTC

from domain.identity.entities import UserRole
from domain.identity.events import (
    UserDeactivated,
    UserLoggedIn,
    UserOAuthLinked,
    UserPasswordChanged,
    UserRegistered,
    UserTwoFactorDisabled,
    UserTwoFactorEnabled,
)
from domain.identity.value_objects import Email
from domain.identity.value_objects import InvalidSecurityReasonError, SecurityReason


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
        forbidden_fragments = ("password", "token", "refresh", "secret", "totp")
        allowed_fields = {"auth_token_version"}
        event_types = [
            UserRegistered,
            UserLoggedIn,
            UserPasswordChanged,
            UserOAuthLinked,
            UserDeactivated,
            UserTwoFactorEnabled,
            UserTwoFactorDisabled,
        ]

        for event_type in event_types:
            event_field_names = {field.name for field in fields(event_type)}
            for field_name in event_field_names:
                if field_name in allowed_fields:
                    continue
                assert not any(fragment in field_name for fragment in forbidden_fragments)

    def test_event_reason_is_security_reason(self):
        event = UserDeactivated(
            user_id=uuid.uuid4(),
            occurred_at=datetime(2025, 1, 1, tzinfo=UTC),
            reason="User requested closure",
        )
        assert isinstance(event.reason, SecurityReason)
        assert str(event.reason) == "User requested closure"

    def test_event_reason_rejects_secret_like_text(self):
        with pytest.raises(InvalidSecurityReasonError):
            UserPasswordChanged(
                user_id=uuid.uuid4(),
                occurred_at=datetime(2025, 1, 1, tzinfo=UTC),
                reason="rotated password after support request",
            )

    def test_auth_token_version_is_version_metadata_not_raw_token(self):
        event = UserPasswordChanged(
            user_id=uuid.uuid4(),
            occurred_at=datetime(2025, 1, 1, tzinfo=UTC),
            auth_token_version=3,
        )
        assert event.auth_token_version == 3
        assert isinstance(event.auth_token_version, int)
        assert "secret" not in repr(event).lower()
        assert "raw-token" not in repr(event)
