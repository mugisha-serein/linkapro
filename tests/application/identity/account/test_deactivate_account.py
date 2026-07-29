import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from application.identity.account import DeactivateAccountUseCase
from application.identity.account.deactivate_account_command import DeactivateUserCommand
from application.identity.errors import UserNotFoundError
from domain.identity.account import User, UserDeactivated, UserRole
from domain.identity.credentials import Email, PasswordHash


class FixedClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=UTC)


def test_deactivate_account_persists_and_dispatches_actor_metadata():
    account_repository = Mock()
    event_outbox = Mock()
    actor_id = uuid.uuid4()
    actor = User(
        id=actor_id,
        email=Email("admin@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    user = User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Active",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_id.side_effect = lambda user_id: {
        actor.id: actor,
        user.id: user,
    }.get(user_id)
    revoke_all_sessions_use_case = Mock()

    DeactivateAccountUseCase(
        account_repository=account_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
        revoke_all_sessions_use_case=revoke_all_sessions_use_case,
    ).execute(
        DeactivateUserCommand(
            user_id=user.id,
            actor_id=actor_id,
            reason="manual admin deactivation",
        )
    )

    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserDeactivated)
    assert event.user_id == user.id
    assert event.actor_user_id == actor_id
    assert str(event.reason) == "manual admin deactivation"
    assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
    revoke_all_sessions_use_case.execute.assert_called_once_with(
        user_id=user.id,
        reason="account_deactivated",
    )


def test_deactivate_account_missing_user_raises_typed_error():
    account_repository = Mock()
    account_repository.get_by_id.return_value = None
    event_outbox = Mock()

    with pytest.raises(UserNotFoundError, match="User not found"):
        DeactivateAccountUseCase(
            account_repository=account_repository,
            event_outbox=event_outbox,
            clock=FixedClock(),
            revoke_all_sessions_use_case=Mock(),
        ).execute(DeactivateUserCommand(user_id=uuid.uuid4()))

    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()
