import uuid
import pytest
import pyotp
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock, ANY

from domain.identity.entities import User, UserRole, OAuthToken
from domain.identity.events import UserDeactivated, UserTwoFactorEnabled
from domain.identity.value_objects import Email, PasswordHash, PlainPassword, OAuthProvider, TOTPSecret
from application.identity.commands import (
    RegisterUserCommand,
    LoginUserCommand,
    LoginTwoFactorCommand,
    OAuthLoginCommand,
    UpdateProfileCommand,
    DeactivateUserCommand,
    VerifyTwoFactorSetupCommand,
)
from application.identity.errors import (
    DuplicateUserError,
    InvalidTwoFactorCodeError,
    UserNotFoundError,
)
from application.identity.handlers import IdentityCommandHandlers
from application.identity.dtos import UserDTO
from application.identity.auth_policy import AuthenticationDecision, AuthenticationStatus


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
    service.create_session_tokens.return_value = ("access_token", "refresh_token")
    return service

@pytest.fixture
def mock_session_store():
    store = Mock()
    store.create_identity_session.return_value = "session-id"
    return store


@pytest.fixture
def mock_event_dispatcher():
    return Mock()


@pytest.fixture
def handlers(
    mock_user_repo,
    mock_oauth_repo,
    mock_password_hasher,
    mock_token_service,
    mock_session_store,
    mock_event_dispatcher,
):
    return IdentityCommandHandlers(
        user_repo=mock_user_repo,
        oauth_repo=mock_oauth_repo,
        password_hasher=mock_password_hasher,
        token_service=mock_token_service,
        session_store=mock_session_store,
        event_dispatcher=mock_event_dispatcher,
    )


class TestRegisterUser:
    def test_successful_registration(self, handlers, mock_user_repo, mock_password_hasher, mock_event_dispatcher):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u

        cmd = RegisterUserCommand(
            email=Email("new@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
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

    def test_registration_uses_self_registration_role_guard(self, handlers, mock_user_repo):
        mock_user_repo.get_by_email.return_value = None

        cmd = RegisterUserCommand(
            email=Email("admin@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        with pytest.raises(ValueError, match="Role cannot self-register"):
            handlers.register_user(cmd)

        mock_user_repo.save.assert_not_called()

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
            plain_password=PlainPassword("StrongPass1!"),
            first_name="A",
            last_name="B",
            role="planner",
        )

        with pytest.raises(DuplicateUserError, match="already exists"):
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
            plain_password=PlainPassword("StrongPass1!"),
        )

        result = handlers.login_user(cmd)

        assert isinstance(result, AuthenticationDecision)
        assert result.status is AuthenticationStatus.AUTHENTICATED
        assert str(result.user.email) == "user@example.com"
        assert result.access_token == "access_token"
        mock_token_service.create_access_token.assert_called_once()
        mock_token_service.create_refresh_token.assert_called_once()
        mock_token_service.create_session_tokens.assert_not_called()
        mock_user_repo.save.assert_called_once()  # last_login updated

    def test_login_invalid_credentials(self, handlers, mock_user_repo, mock_password_hasher):
        mock_user_repo.get_by_email.return_value = None

        cmd = LoginUserCommand(
            email=Email("wrong@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
        )

        result = handlers.login_user(cmd)
        assert result.status is AuthenticationStatus.INVALID_CREDENTIALS

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
            plain_password=PlainPassword("StrongPass1!"),
        )

        result = handlers.login_user(cmd)
        assert result.status is AuthenticationStatus.INACTIVE

    def test_login_requires_two_factor(self, handlers, mock_user_repo, mock_password_hasher, mock_token_service):
        user = User(
            id=uuid.uuid4(),
            email=Email("mfa@example.com"),
            password_hash=PasswordHash("hashed"),
            first_name="MFA",
            last_name="User",
            role=UserRole.PLANNER,
            is_active=True,
            two_factor_enabled=True,
        )
        mock_user_repo.get_by_email.return_value = user
        mock_password_hasher.verify.return_value = True
        mock_token_service.create_temp_token.return_value = "temp_token"

        cmd = LoginUserCommand(
            email=Email("mfa@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
        )

        result = handlers.login_user(cmd)

        assert result.status is AuthenticationStatus.MFA_REQUIRED
        assert result.temp_token == "temp_token"
        mock_token_service.create_temp_token.assert_called_once_with(str(user.id))
        mock_token_service.create_access_token.assert_not_called()
        mock_token_service.create_refresh_token.assert_not_called()
        mock_token_service.create_session_tokens.assert_not_called()


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

        assert isinstance(result, AuthenticationDecision)
        assert result.status is AuthenticationStatus.AUTHENTICATED
        # User is saved twice: once after creation, once after record_login()
        assert mock_user_repo.save.call_count == 2
        assert mock_oauth_repo.save.call_count == 2
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
        oauth_token = OAuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google123",
            access_token="old_access",
            refresh_token="old_refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
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
        assert oauth_token.access_token.reveal_for_provider_sync() == "new_access"
        assert result.status is AuthenticationStatus.AUTHENTICATED


class TestUpdateProfile:
    def test_missing_user_raises_typed_error(self, handlers, mock_user_repo):
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(UserNotFoundError, match="User not found"):
            handlers.update_profile(UpdateProfileCommand(user_id=uuid.uuid4(), first_name="New"))

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

    def test_update_fields_uses_domain_name_validation(self, handlers, mock_user_repo):
        user = User(
            id=uuid.uuid4(),
            email=Email("user@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Old",
            last_name="Name",
            role=UserRole.PLANNER,
        )
        mock_user_repo.get_by_id.return_value = user

        cmd = UpdateProfileCommand(user_id=user.id, first_name="   ")

        with pytest.raises(ValueError, match="cannot be empty"):
            handlers.update_profile(cmd)

        mock_user_repo.save.assert_not_called()


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
        event = mock_event_dispatcher.dispatch.call_args.args[0]
        assert isinstance(event, UserDeactivated)
        assert event.user_id == user.id
        assert event.auth_token_version == user.auth_token_version


class TestTwoFactorSetup:
    def test_verify_setup_enables_user_through_entity(self, handlers, mock_user_repo, mock_event_dispatcher, monkeypatch):
        user = User(
            id=uuid.uuid4(),
            email=Email("mfa@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="MFA",
            last_name="User",
            role=UserRole.PLANNER,
        )
        secret = pyotp.random_base32()
        token = pyotp.TOTP(secret).now()
        mock_user_repo.get_by_id.return_value = user
        monkeypatch.setattr(
            "application.identity.handlers.cache.get",
            lambda key: secret if key == f"totp_setup_{user.id}" else None,
        )
        cache_set = Mock()
        monkeypatch.setattr("application.identity.handlers.cache.set", cache_set)
        monkeypatch.setattr("application.identity.handlers.cache.delete", Mock())

        handlers.verify_two_factor_setup(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

        assert user.two_factor_enabled is True
        cache_set.assert_called_once_with(f"totp_used_{user.id}_{token}", "1", timeout=90)
        mock_user_repo.set_totp_secret.assert_called_once()
        mock_user_repo.save.assert_called_once_with(user)
        event = mock_event_dispatcher.dispatch.call_args.args[0]
        assert isinstance(event, UserTwoFactorEnabled)
        assert event.user_id == user.id
        assert event.auth_token_version == user.auth_token_version

    def test_verify_setup_rejects_replayed_totp_token(self, handlers, mock_user_repo, monkeypatch):
        user = User(
            id=uuid.uuid4(),
            email=Email("mfa@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="MFA",
            last_name="User",
            role=UserRole.PLANNER,
        )
        secret = pyotp.random_base32()
        token = pyotp.TOTP(secret).now()
        mock_user_repo.get_by_id.return_value = user
        monkeypatch.setattr(
            "application.identity.handlers.cache.get",
            lambda key: secret if key == f"totp_setup_{user.id}" else "1",
        )
        cache_set = Mock()
        monkeypatch.setattr("application.identity.handlers.cache.set", cache_set)

        with pytest.raises(InvalidTwoFactorCodeError, match="Invalid TOTP token"):
            handlers.verify_two_factor_setup(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

        cache_set.assert_not_called()

    def test_verify_setup_invalid_token_raises_typed_error(self, handlers, mock_user_repo, monkeypatch):
        user = User(
            id=uuid.uuid4(),
            email=Email("mfa@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="MFA",
            last_name="User",
            role=UserRole.PLANNER,
        )
        secret = pyotp.random_base32()
        mock_user_repo.get_by_id.return_value = user
        monkeypatch.setattr("application.identity.handlers.cache.get", lambda key: secret)

        with pytest.raises(InvalidTwoFactorCodeError, match="Invalid TOTP token"):
            handlers.verify_two_factor_setup(VerifyTwoFactorSetupCommand(user_id=user.id, token="000000"))

    def test_login_two_factor_rejects_replayed_totp_token(self, handlers, mock_user_repo, mock_token_service, monkeypatch):
        user = User(
            id=uuid.uuid4(),
            email=Email("mfa-login@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="MFA",
            last_name="Login",
            role=UserRole.PLANNER,
        )
        secret = pyotp.random_base32()
        token = pyotp.TOTP(secret).now()
        mock_token_service.verify_temp_token.return_value = {"user_id": str(user.id)}
        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.get_totp_secret.return_value = TOTPSecret(secret)
        monkeypatch.setattr("application.identity.handlers.cache.get", lambda key: "1")
        cache_set = Mock()
        monkeypatch.setattr("application.identity.handlers.cache.set", cache_set)

        result = handlers.login_two_factor(LoginTwoFactorCommand(temp_token="temp", token=token))

        assert result.status is AuthenticationStatus.INVALID_MFA_CODE
        cache_set.assert_not_called()
        mock_user_repo.save.assert_not_called()
