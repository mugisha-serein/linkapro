import uuid
from unittest.mock import Mock

import pytest

from application.identity.account import UpdateAccountProfileUseCase
from application.identity.commands import UpdateProfileCommand
from application.identity.errors import UserNotFoundError
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash


def test_update_account_profile_persists_valid_name_change():
    account_repository = Mock()
    user = User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Old",
        last_name="Name",
        role=UserRole.PLANNER,
    )
    account_repository.get_by_id.return_value = user
    account_repository.save.side_effect = lambda saved_user: saved_user

    result = UpdateAccountProfileUseCase(account_repository=account_repository).execute(
        UpdateProfileCommand(user_id=user.id, first_name=" New ", last_name=" Person ")
    )

    account_repository.save.assert_called_once_with(user)
    assert result.first_name == "New"
    assert result.last_name == "Person"


def test_update_account_profile_missing_user_raises_typed_error():
    account_repository = Mock()
    account_repository.get_by_id.return_value = None

    with pytest.raises(UserNotFoundError, match="User not found"):
        UpdateAccountProfileUseCase(account_repository=account_repository).execute(
            UpdateProfileCommand(user_id=uuid.uuid4(), first_name="New")
        )

    account_repository.save.assert_not_called()
