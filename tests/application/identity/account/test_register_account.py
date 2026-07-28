import uuid
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from application.identity.account import RegisterAccountUseCase
from application.identity.commands import RegisterUserCommand
from application.identity.errors import DuplicateUserError
from domain.identity.account import AccountRole, User, UserRegistered, UserRole
from domain.identity.credentials import Email, PasswordHash, PlainPassword


class FixedClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=UTC)


class FixedIdGenerator:
    def new_id(self):
        return uuid.UUID("11111111-1111-4111-8111-111111111111")


def _use_case(account_repository, password_hasher, event_outbox):
    return RegisterAccountUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=event_outbox,
        clock=FixedClock(),
        id_generator=FixedIdGenerator(),
    )


class RecordingUnitOfWork:
    def __init__(self):
        self.entered = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or not self.committed:
            self.rolled_back = True
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_register_account_persists_user_and_dispatches_recorded_event():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    account_repository.save.side_effect = lambda user: user
    password_hasher = Mock()
    password_hasher.hash.return_value = "hashed-password"
    event_outbox = Mock()

    result = _use_case(account_repository, password_hasher, event_outbox).execute(
        RegisterUserCommand(
            email=Email("new@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
            first_name="New",
            last_name="User",
            role=AccountRole.PLANNER,
        )
    )

    saved_user = account_repository.save.call_args.args[0]
    event = event_outbox.dispatch.call_args.args[0]
    assert saved_user.id == uuid.UUID("11111111-1111-4111-8111-111111111111")
    assert saved_user.password_hash == PasswordHash("hashed-password")
    assert isinstance(event, UserRegistered)
    assert event.user_id == saved_user.id
    assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert result.email == "new@example.com"


def test_register_account_commits_unit_of_work_after_all_writes():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    account_repository.save.side_effect = lambda user: user
    password_hasher = Mock()
    password_hasher.hash.return_value = "hashed-password"
    event_outbox = Mock()
    unit_of_work = RecordingUnitOfWork()

    RegisterAccountUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=event_outbox,
        clock=FixedClock(),
        id_generator=FixedIdGenerator(),
        unit_of_work=unit_of_work,
    ).execute(
        RegisterUserCommand(
            email=Email("uow@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
            first_name="Unit",
            last_name="Work",
            role=AccountRole.PLANNER,
        )
    )

    assert unit_of_work.entered is True
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False


def test_register_account_rolls_back_unit_of_work_when_event_dispatch_fails():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    account_repository.save.side_effect = lambda user: user
    password_hasher = Mock()
    password_hasher.hash.return_value = "hashed-password"
    event_outbox = Mock()
    event_outbox.dispatch.side_effect = RuntimeError("outbox failed")
    unit_of_work = RecordingUnitOfWork()

    with pytest.raises(RuntimeError, match="outbox failed"):
        RegisterAccountUseCase(
            account_repository=account_repository,
            password_hasher=password_hasher,
            event_outbox=event_outbox,
            clock=FixedClock(),
            id_generator=FixedIdGenerator(),
            unit_of_work=unit_of_work,
        ).execute(
            RegisterUserCommand(
                email=Email("rollback@example.com"),
                plain_password=PlainPassword("StrongPass1!"),
                first_name="Roll",
                last_name="Back",
                role=AccountRole.PLANNER,
            )
        )

    assert account_repository.save.called is True
    assert unit_of_work.entered is True
    assert unit_of_work.committed is False
    assert unit_of_work.rolled_back is True


def test_register_account_rejects_duplicate_email():
    existing_user = User(
        id=uuid.uuid4(),
        email=Email("exists@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Existing",
        last_name="User",
        role=UserRole.PLANNER,
    )
    account_repository = Mock()
    account_repository.get_by_email.return_value = existing_user
    password_hasher = Mock()
    event_outbox = Mock()

    with pytest.raises(DuplicateUserError, match="already exists"):
        _use_case(account_repository, password_hasher, event_outbox).execute(
            RegisterUserCommand(
                email=Email("exists@example.com"),
                plain_password=PlainPassword("StrongPass1!"),
                first_name="Existing",
                last_name="User",
                role=AccountRole.PLANNER,
            )
        )

    password_hasher.hash.assert_not_called()
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()
