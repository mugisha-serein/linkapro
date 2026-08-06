import uuid
import pytest
from unittest.mock import Mock

from application.identity.account_lockout import AccountLockoutConfig, AccountLockoutService
from application.identity.authentication import (
    AuthenticationDecision,
    AuthenticationStatus,
    AuthenticatedSessionIssuer,
    LoginWithPasswordUseCase,
)
from application.identity.authentication.login_with_password_command import LoginUserCommand
from domain.identity.account import User, UserRole
from domain.identity.authentication import FailedAttemptCounter
from domain.identity.credentials import Email, PasswordHash, PlainPassword


def _token_service():
    service = Mock()
    service.create_access_token.return_value = "access-token"
    service.create_refresh_token.return_value = "refresh-token"
    service.create_temp_token.return_value = "temp-token"
    return service


def _session_store():
    store = Mock()
    store.create_identity_session.return_value = "session-id"
    return store


def _lockout_service():
    repo = Mock()
    repo.load_failed_attempt_counter.return_value = FailedAttemptCounter()
    return AccountLockoutService(
        repository=repo,
        config=AccountLockoutConfig(
            max_failures=5,
            observation_window_seconds=900,
            lock_duration_seconds=600,
        ),
    )


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.VENDOR, UserRole.PLANNER])
def test_login_with_password_succeeds_for_all_roles(role):
    account_repository = Mock()
    password_hasher = Mock()
    password_hasher.verify.return_value = True
    event_outbox = Mock()

    user = User(
        id=uuid.uuid4(),
        email=Email(f"{role.value}@example.com"),
        password_hash=PasswordHash("hashed_pass"),
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_email.return_value = user

    session_issuer = AuthenticatedSessionIssuer(
        _token_service(),
        _session_store(),
        mfa_challenge_repository=Mock(),
    )
    use_case = LoginWithPasswordUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=event_outbox,
        account_lockout_service=_lockout_service(),
        session_issuer=session_issuer,
    )

    cmd = LoginUserCommand(
        email=Email(f"{role.value}@example.com"),
        plain_password=PlainPassword("ValidPass1!"),
    )
    decision = use_case.execute(cmd)

    assert decision.status is AuthenticationStatus.AUTHENTICATED
    assert decision.user.role == role
    assert decision.access_token == "access-token"
    assert decision.refresh_token == "refresh-token"


def test_login_with_password_returns_user_not_found_when_account_missing():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    password_hasher = Mock()

    use_case = LoginWithPasswordUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=Mock(),
        account_lockout_service=_lockout_service(),
        session_issuer=Mock(),
    )

    cmd = LoginUserCommand(
        email=Email("nonexistent@example.com"),
        plain_password=PlainPassword("ValidPass1!"),
    )
    decision = use_case.execute(cmd)

    assert decision.status is AuthenticationStatus.USER_NOT_FOUND
    password_hasher.verify_against_dummy.assert_called_once_with(cmd.plain_password)


def test_login_with_password_returns_password_mismatch_on_wrong_password():
    account_repository = Mock()
    password_hasher = Mock()
    password_hasher.verify.return_value = False

    user = User(
        id=uuid.uuid4(),
        email=Email("vendor@example.com"),
        password_hash=PasswordHash("hashed_pass"),
        first_name="Vendor",
        last_name="User",
        role=UserRole.VENDOR,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_email.return_value = user

    session_issuer = AuthenticatedSessionIssuer(
        _token_service(),
        _session_store(),
        mfa_challenge_repository=Mock(),
    )
    use_case = LoginWithPasswordUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=Mock(),
        account_lockout_service=_lockout_service(),
        session_issuer=session_issuer,
    )

    cmd = LoginUserCommand(
        email=Email("vendor@example.com"),
        plain_password=PlainPassword("WrongPass1!"),
    )
    decision = use_case.execute(cmd)

    assert decision.status is AuthenticationStatus.PASSWORD_MISMATCH
