import uuid
from unittest.mock import Mock

import pytest

from application.identity.commands import ChangePasswordCommand, SetupPasswordCommand
from application.identity.credentials import ChangePasswordUseCase, SetupPasswordUseCase
from application.identity.errors import InvalidCredentialsError
from domain.identity.account import User, UserRole
from domain.identity.credentials import (
    Email,
    PasswordHash,
    PasswordHistory,
    PasswordReuseNotAllowed,
    PlainPassword,
    UserPasswordChanged,
    WeakPasswordError,
)


class FakeHasher:
    def hash(self, plain: PlainPassword) -> str:
        return f"hash:{plain.value}"

    def verify(self, plain: PlainPassword | str, hashed: PasswordHash) -> bool:
        value = plain.value if hasattr(plain, "value") else str(plain)
        return hashed.reveal_for_password_verification() == f"hash:{value}"

    def verify_against_dummy(self, password: PlainPassword) -> None:
        return None


def _user(password_hash: PasswordHash | None = PasswordHash("hash:CurrentPass1!")) -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=password_hash,
        first_name="Test",
        last_name="User",
        role=UserRole.PLANNER,
        is_verified=True,
    )


def test_change_password_validates_history_and_dispatches_entity_event():
    user = _user()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    account_repository.get_password_history.return_value = PasswordHistory([PasswordHash("hash:CurrentPass1!")])
    account_repository.save.side_effect = lambda saved_user: saved_user
    event_outbox = Mock()

    ChangePasswordUseCase(
        account_repository=account_repository,
        password_hasher=FakeHasher(),
        event_outbox=event_outbox,
    ).execute(
        ChangePasswordCommand(
            user_id=user.id,
            current_password=PlainPassword("CurrentPass1!"),
            new_password=PlainPassword("NextValidPass1!"),
        )
    )

    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert user.password_hash == PasswordHash("hash:NextValidPass1!")
    assert isinstance(event, UserPasswordChanged)
    assert event.user_id == user.id


def test_change_password_rejects_wrong_current_password():
    user = _user()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    event_outbox = Mock()

    with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
        ChangePasswordUseCase(
            account_repository=account_repository,
            password_hasher=FakeHasher(),
            event_outbox=event_outbox,
        ).execute(
            ChangePasswordCommand(
                user_id=user.id,
                current_password=PlainPassword("WrongPass1!"),
                new_password=PlainPassword("NextValidPass1!"),
            )
        )

    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_change_password_rejects_weak_new_password_before_hashing():
    user = _user()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    event_outbox = Mock()

    with pytest.raises(WeakPasswordError):
        ChangePasswordUseCase(
            account_repository=account_repository,
            password_hasher=FakeHasher(),
            event_outbox=event_outbox,
        ).execute(
            ChangePasswordCommand(
                user_id=user.id,
                current_password=PlainPassword("CurrentPass1!"),
                new_password=PlainPassword("weakpass"),
            )
        )

    account_repository.get_password_history.assert_not_called()
    account_repository.save.assert_not_called()


def test_setup_password_rejects_recently_used_password():
    user = _user(password_hash=None)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    account_repository.get_password_history.return_value = PasswordHistory([PasswordHash("hash:OldValidPass1!")])
    event_outbox = Mock()

    with pytest.raises(PasswordReuseNotAllowed):
        SetupPasswordUseCase(
            account_repository=account_repository,
            password_hasher=FakeHasher(),
            event_outbox=event_outbox,
        ).execute(
            SetupPasswordCommand(
                user_id=user.id,
                plain_password=PlainPassword("OldValidPass1!"),
            )
        )

    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_setup_password_persists_and_returns_user_dto():
    user = _user(password_hash=None)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    account_repository.get_password_history.return_value = PasswordHistory()
    account_repository.save.side_effect = lambda saved_user: saved_user
    event_outbox = Mock()

    result = SetupPasswordUseCase(
        account_repository=account_repository,
        password_hasher=FakeHasher(),
        event_outbox=event_outbox,
    ).execute(
        SetupPasswordCommand(
            user_id=user.id,
            plain_password=PlainPassword("SetupValidPass1!"),
        )
    )

    assert result.id == user.id
    assert result.has_password is True
    assert user.password_hash == PasswordHash("hash:SetupValidPass1!")
    assert isinstance(event_outbox.dispatch.call_args.args[0], UserPasswordChanged)
