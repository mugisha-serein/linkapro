import uuid
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, ANY

from domain.identity.entities import User, UserRole
from domain.identity.value_objects import Email, PasswordHash, PlainPassword, OAuthProvider
from application.identity.commands import (
    RegisterUserCommand,
    LoginUserCommand,
    OAuthLoginCommand,
    ChangePasswordCommand,
    UpdateProfileCommand,
    DeactivateUserCommand,
)
from application.identity.handlers import IdentityCommandHandlers
from application.identity.dtos import UserDTO, AuthenticationResultDTO


@pytest.fixture
def mock_user_repo():
    return Mock()

@pytest.fixture
def mock_oauth_repo():
    return Mock()

@pytest.fixture
def mock_password_hasher():
    hasher = Mock()
    hasher.hash.return_value = "hashed_password"
    hasher.verify.return_value = True
    return hasher

@pytest.fixture
def mock_token_service():
    service = Mock()
    service.create_access_token.return_value = "access_token"
    service.create_refresh_token.return_value = "refresh_token"
    return service

@pytest.fixture
def mock_event_dispatcher():
    return Mock()

@pytest.fixture
def handlers(mock_user_repo, mock_oauth_repo, mock_password_hasher, mock_token_service, mock_event_dispatcher):
    return IdentityCommandHandlers(
        user_repo=mock_user_repo,
        oauth_repo=mock_oauth_repo,
        password_hasher=mock_password_hasher,
        token_service=mock_token_service,
        event_dispatcher=mock_event_dispatcher,
    )


class TestRegisterUser:
    def test_successful_registration(self, handlers, mock_user_repo, mock_password_hasher, mock_event_dispatcher):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u

        cmd = RegisterUserCommand(
            email=Email("new@example.com"),
            plain_password=PlainPassword("StrongPass1"),
            first_name="New",
            last_name="User",
            role="planner",
        )

        result = handlers.register_user(cmd)

        mock_user_repo.get_by_email.assert_called_once()
        mock_password_hasher.hash.assert_called_once()
        mock_user_repo.save.assert_called_once()
        mock_event_dispatcher.dispatch.assert_called_once()

        assert isinstance(result, UserDTO)
        assert result.email == "new@example.com"
        assert result.role == "planner"

    def test_register_with_existing_email_raises_error(self, handlers, mock_user_repo):
        existing_user = User(
            id=uuid.uuid4(),
            email=Email("exists@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
        )
        mock_user_repo.get_by_email.return_value = existing_user

        cmd = RegisterUserCommand(
            email=Email("exists@example.com"),
            plain_password=PlainPassword("StrongPass1"),
            first_name="A",
            last_name="B",
            role="planner",
        )

        with pytest.raises(ValueError, match="already exists"):
            handlers.register_user(cmd)


class TestLoginUser:
    def test_successful_login(self, handlers, mock_user_repo, mock_password_hasher, mock_token_service):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("hashed"),
            first_name="Test",
            last_name="User",
            role=UserRole.PLANNER,
            is_active=True,
        )
        mock_user_repo.get_by_email.return_value = user
        mock_password_hasher.verify.return_value = True

        cmd = LoginUserCommand(
            email=Email("user@example.com"),
            plain_password=PlainPassword("StrongPass1"),
        )

        result = handlers.login_user(cmd)

        assert isinstance(result, AuthenticationResultDTO)
        assert result.user.email == "user@example.com"
        assert result.access_token == "access_token"
        mock_token_service.create_access_token.assert_called_once()
        mock_user_repo.save.assert_called_once()  # last_login updated

    def test_login_invalid_credentials(self, handlers, mock_user_repo, mock_password_hasher):
        mock_user_repo.get_by_email.return_value = None

        cmd = LoginUserCommand(
            email=Email("wrong@example.com"),
            plain_password=PlainPassword("StrongPass1"),
        )

        with pytest.raises(ValueError, match="Invalid credentials"):
            handlers.login_user(cmd)

    def test_login_deactivated_user(self, handlers, mock_user_repo):
        user = User(
            id=uuid.uuid4(),
            email=Email("deactivated@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
            is_active=False,
        )
        mock_user_repo.get_by_email.return_value = user

        cmd = LoginUserCommand(
            email=Email("deactivated@example.com"),
            plain_password=PlainPassword("StrongPass1"),
        )

        with pytest.raises(ValueError, match="deactivated"):
            handlers.login_user(cmd)


class TestOAuthLogin:
    def test_new_oauth_user(self, handlers, mock_user_repo, mock_oauth_repo, mock_token_service):
        mock_oauth_repo.get_by_provider_and_user.return_value = None
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u
        mock_oauth_repo.save.side_effect = lambda t: t

        cmd = OAuthLoginCommand(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google123",
            email=Email("oauth@example.com"),
            first_name="OAuth",
            last_name="User",
            access_token="access123",
            refresh_token="refresh123",
            expires_in=3600,
        )

        result = handlers.oauth_login(cmd)

        assert isinstance(result, AuthenticationResultDTO)
        # User is saved twice: once after creation, once after record_login()
        assert mock_user_repo.save.call_count == 2
        mock_oauth_repo.save.assert_called_once()
        # At least two events are dispatched: UserOAuthLinked and UserRegistered
        assert handlers.event_dispatcher.dispatch.call_count >= 2

    def test_existing_oauth_user_updates_token(self, handlers, mock_user_repo, mock_oauth_repo):
        user = User(
            id=uuid.uuid4(),
            email=Email("existing@example.com"),
            password_hash=None,
            first_name="Old",
            last_name="User",
            role=UserRole.PLANNER,
        )
        oauth_token = Mock()
        oauth_token.user_id = user.id
        mock_oauth_repo.get_by_provider_and_user.return_value = oauth_token
        mock_user_repo.get_by_id.return_value = user

        cmd = OAuthLoginCommand(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google123",
            email=Email("existing@example.com"),
            first_name="Old",
            last_name="User",
            access_token="new_access",
            refresh_token="new_refresh",
            expires_in=3600,
        )

        result = handlers.oauth_login(cmd)

        mock_oauth_repo.save.assert_called_once()
        assert oauth_token.access_token == "new_access"


class TestChangePassword:
    def test_successful_change(self, handlers, mock_user_repo, mock_password_hasher, mock_event_dispatcher):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("old_hash"),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
        )
        mock_user_repo.get_by_id.return_value = user
        mock_password_hasher.verify.return_value = True

        cmd = ChangePasswordCommand(
            user_id=user.id,
            old_plain_password=PlainPassword("OldPass1"),
            new_plain_password=PlainPassword("NewPass1"),
        )

        handlers.change_password(cmd)

        mock_password_hasher.verify.assert_called_once()
        mock_password_hasher.hash.assert_called_once()
        mock_user_repo.save.assert_called_once()
        mock_event_dispatcher.dispatch.assert_called_once()

    def test_incorrect_old_password_raises(self, handlers, mock_user_repo, mock_password_hasher):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
        )
        mock_user_repo.get_by_id.return_value = user
        mock_password_hasher.verify.return_value = False

        cmd = ChangePasswordCommand(
            user_id=user.id,
            old_plain_password=PlainPassword("WrongPass1"),
            new_plain_password=PlainPassword("NewPass1"),
        )

        with pytest.raises(ValueError, match="incorrect"):
            handlers.change_password(cmd)


class TestUpdateProfile:
    def test_update_fields(self, handlers, mock_user_repo):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Old",
            last_name="Name",
            role=UserRole.PLANNER,
        )
        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        cmd = UpdateProfileCommand(
            user_id=user.id,
            first_name="NewFirst",
            last_name="NewLast",
        )

        result = handlers.update_profile(cmd)

        assert result.first_name == "NewFirst"
        assert result.last_name == "NewLast"
        mock_user_repo.save.assert_called_once()


class TestDeactivateUser:
    def test_deactivate(self, handlers, mock_user_repo, mock_event_dispatcher):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="A",
            last_name="B",
            role=UserRole.PLANNER,
            is_active=True,
        )
        mock_user_repo.get_by_id.return_value = user

        cmd = DeactivateUserCommand(user_id=user.id)
        handlers.deactivate_user(cmd)

        assert user.is_active is False
        mock_user_repo.save.assert_called_once()
        mock_event_dispatcher.dispatch.assert_called_once()