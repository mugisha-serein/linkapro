import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from application.identity.authorization import (
    AssignRoleUseCase,
    ReactivateAccountUseCase,
    SuspendAccountUseCase,
    UnlockAccountUseCase,
)
from application.identity.authorization.assign_role_command import AssignRoleCommand
from application.identity.authorization.reactivate_account_command import ReactivateAccountCommand
from application.identity.authorization.suspend_account_command import SuspendAccountCommand
from application.identity.authorization.unlock_account_command import UnlockAccountCommand
from domain.identity.account import (
    AccountStatus,
    User,
    UserActivated,
    UserRole,
    UserSuspended,
    UserUnlocked,
)
from domain.identity.authorization import RoleAssignmentDenied, UserRoleChanged
from domain.identity.credentials import Email, PasswordHash
from domain.identity.shared.security_reason import SecurityReason


class FixedClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=UTC)


def _user(*, role=UserRole.PLANNER, status=AccountStatus.ACTIVE) -> User:
    return User(
        id=uuid.uuid4(),
        email=Email(f"{uuid.uuid4()}@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Test",
        last_name="User",
        role=role,
        status=status,
        is_active=True,
        is_verified=True,
    )


def _repo(actor: User, target: User):
    repository = Mock()
    repository.get_by_id.side_effect = lambda user_id: {
        actor.id: actor,
        target.id: target,
    }.get(user_id)
    return repository


def test_assign_role_consults_policy_then_dispatches_recorded_event():
    actor = _user(role=UserRole.ADMIN)
    target = _user(role=UserRole.PLANNER)
    account_repository = _repo(actor, target)
    event_outbox = Mock()

    AssignRoleUseCase(
        account_repository=account_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
    ).execute(
        AssignRoleCommand(
            actor_id=actor.id,
            target_user_id=target.id,
            new_role=UserRole.VENDOR,
            reason=SecurityReason("support request"),
        )
    )

    account_repository.save.assert_called_once_with(target)
    event = event_outbox.dispatch.call_args.args[0]
    assert target.role is UserRole.VENDOR
    assert isinstance(event, UserRoleChanged)
    assert event.actor_user_id == actor.id
    assert str(event.reason) == "support request"


def test_assign_role_rejects_unauthorized_actor():
    actor = _user(role=UserRole.PLANNER)
    target = _user(role=UserRole.PLANNER)
    account_repository = _repo(actor, target)
    event_outbox = Mock()

    with pytest.raises(RoleAssignmentDenied):
        AssignRoleUseCase(
            account_repository=account_repository,
            event_outbox=event_outbox,
            clock=FixedClock(),
        ).execute(
            AssignRoleCommand(
                actor_id=actor.id,
                target_user_id=target.id,
                new_role=UserRole.VENDOR,
            )
        )

    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_suspend_account_uses_actor_policy_and_records_actor_metadata():
    actor = _user(role=UserRole.ADMIN)
    target = _user()
    account_repository = _repo(actor, target)
    event_outbox = Mock()
    revoke_all_sessions_use_case = Mock()

    SuspendAccountUseCase(
        account_repository=account_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
        revoke_all_sessions_use_case=revoke_all_sessions_use_case,
    ).execute(
        SuspendAccountCommand(
            actor_id=actor.id,
            target_user_id=target.id,
            reason=SecurityReason("terms violation"),
        )
    )

    event = event_outbox.dispatch.call_args.args[0]
    assert target.status is AccountStatus.SUSPENDED
    assert isinstance(event, UserSuspended)
    assert event.actor_user_id == actor.id
    assert str(event.reason) == "terms violation"
    revoke_all_sessions_use_case.execute.assert_called_once_with(
        user_id=target.id,
        reason="account_suspended",
    )


def test_reactivate_account_records_actor_metadata():
    actor = _user(role=UserRole.ADMIN)
    target = _user(status=AccountStatus.DEACTIVATED)
    account_repository = _repo(actor, target)
    event_outbox = Mock()

    ReactivateAccountUseCase(
        account_repository=account_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
    ).execute(
        ReactivateAccountCommand(
            actor_id=actor.id,
            target_user_id=target.id,
            reason="appeal accepted",
        )
    )

    event = event_outbox.dispatch.call_args.args[0]
    assert target.status is AccountStatus.ACTIVE
    assert isinstance(event, UserActivated)
    assert event.actor_user_id == actor.id
    assert str(event.reason) == "appeal accepted"


def test_unlock_account_records_actor_metadata():
    actor = _user(role=UserRole.ADMIN)
    target = _user(status=AccountStatus.LOCKED)
    account_repository = _repo(actor, target)
    event_outbox = Mock()

    UnlockAccountUseCase(
        account_repository=account_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
    ).execute(
        UnlockAccountCommand(
            actor_id=actor.id,
            target_user_id=target.id,
            reason="manual unlock",
        )
    )

    event = event_outbox.dispatch.call_args.args[0]
    assert target.status is AccountStatus.ACTIVE
    assert isinstance(event, UserUnlocked)
    assert event.actor_user_id == actor.id
    assert str(event.reason) == "manual unlock"
