import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from application.identity.account_lockout import AccountLockoutConfig, AccountLockoutService
from application.identity.authentication import AuthenticationStatus, AuthenticatedSessionIssuer
from application.identity.authentication import LoginWithPasswordUseCase
from application.identity.authentication.login_with_password_command import LoginUserCommand
from domain.identity.account import User, UserRole
from domain.identity.authentication import FailedAttemptCounter
from domain.identity.authentication import UserLoggedIn
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


class MemoryAuthenticationAttemptRepository:
    def __init__(self):
        self.counters = {}

    def load_failed_attempt_counter(self, account_key):
        return self.counters.get(account_key, FailedAttemptCounter())

    def save_failed_attempt_counter(
        self,
        account_key,
        counter,
        *,
        observation_window_seconds,
        lock_duration_seconds,
    ):
        self.counters[account_key] = counter

    def clear_failed_attempt_counter(self, account_key):
        self.counters.pop(account_key, None)


def _lockout_service(repository=None, *, max_failures=2):
    return AccountLockoutService(
        repository=repository or MemoryAuthenticationAttemptRepository(),
        config=AccountLockoutConfig(
            max_failures=max_failures,
            observation_window_seconds=900,
            lock_duration_seconds=600,
        ),
        now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _use_case(
    account_repository,
    password_hasher,
    event_outbox,
    token_service=None,
    session_store=None,
    mfa_challenge_repository=None,
    account_lockout_service=None,
):
    token_service = token_service or _token_service()
    session_store = session_store or _session_store()
    mfa_challenge_repository = mfa_challenge_repository or Mock()
    return LoginWithPasswordUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        event_outbox=event_outbox,
        account_lockout_service=account_lockout_service or _lockout_service(),
        session_issuer=AuthenticatedSessionIssuer(
            token_service,
            session_store,
            mfa_challenge_repository=mfa_challenge_repository,
        ),
    )


def test_login_with_password_invokes_dummy_hash_for_unknown_account():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    password_hasher = Mock()
    event_outbox = Mock()
    cmd = LoginUserCommand(
        email=Email("missing@example.com"),
        plain_password=PlainPassword("StrongPass1!"),
    )

    decision = _use_case(account_repository, password_hasher, event_outbox).execute(cmd)

    assert decision.status is AuthenticationStatus.USER_NOT_FOUND
    password_hasher.verify_against_dummy.assert_called_once_with(cmd.plain_password)
    password_hasher.verify.assert_not_called()
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_login_with_password_locks_after_invalid_credentials_threshold():
    account_repository = Mock()
    account_repository.get_by_email.return_value = None
    password_hasher = Mock()
    event_outbox = Mock()
    attempts = MemoryAuthenticationAttemptRepository()
    use_case = _use_case(
        account_repository,
        password_hasher,
        event_outbox,
        account_lockout_service=_lockout_service(attempts, max_failures=2),
    )
    cmd = LoginUserCommand(
        email=Email("missing@example.com"),
        plain_password=PlainPassword("StrongPass1!"),
    )

    first = use_case.execute(cmd)
    second = use_case.execute(cmd)
    third = use_case.execute(cmd)

    assert first.status is AuthenticationStatus.USER_NOT_FOUND
    assert second.status is AuthenticationStatus.LOCKED
    assert third.status is AuthenticationStatus.LOCKED
    assert password_hasher.verify_against_dummy.call_count == 2


def test_login_with_password_distinguishes_password_mismatch():
    account_repository = Mock()
    password_hasher = Mock()
    password_hasher.verify.return_value = False
    event_outbox = Mock()
    user = User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hashed"),
        first_name="Login",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_email.return_value = user

    decision = _use_case(account_repository, password_hasher, event_outbox).execute(
        LoginUserCommand(
            email=Email("user@example.com"),
            plain_password=PlainPassword("WrongPass1!"),
        )
    )

    assert decision.status is AuthenticationStatus.PASSWORD_MISMATCH
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_login_with_password_authenticates_admin_vendor_and_planner_roles():
    for role in (UserRole.ADMIN, UserRole.VENDOR, UserRole.PLANNER):
        account_repository = Mock()
        password_hasher = Mock()
        password_hasher.verify.return_value = True
        event_outbox = Mock()
        user = User(
            id=uuid.uuid4(),
            email=Email(f"{role.value}@example.com"),
            password_hash=PasswordHash("hashed"),
            first_name=role.value.title(),
            last_name="User",
            role=role,
            is_active=True,
            is_verified=True,
        )
        account_repository.get_by_email.return_value = user

        decision = _use_case(account_repository, password_hasher, event_outbox).execute(
            LoginUserCommand(
                email=user.email,
                plain_password=PlainPassword("StrongPass1!"),
            )
        )

        assert decision.status is AuthenticationStatus.AUTHENTICATED
        assert decision.user.role is role
        account_repository.save.assert_called_once_with(user)


def test_login_with_password_persists_login_event_after_success():
    account_repository = Mock()
    password_hasher = Mock()
    password_hasher.verify.return_value = True
    event_outbox = Mock()
    user = User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hashed"),
        first_name="Login",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_email.return_value = user

    decision = _use_case(account_repository, password_hasher, event_outbox).execute(
        LoginUserCommand(
            email=Email("user@example.com"),
            plain_password=PlainPassword("StrongPass1!"),
        )
    )

    assert decision.status is AuthenticationStatus.AUTHENTICATED
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserLoggedIn)
    assert event.user_id == user.id


def test_login_with_password_clears_failed_attempts_after_password_success():
    attempts = MemoryAuthenticationAttemptRepository()
    account_repository = Mock()
    password_hasher = Mock()
    password_hasher.verify.return_value = True
    event_outbox = Mock()
    user = User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hashed"),
        first_name="Login",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    account_repository.get_by_email.return_value = user
    service = _lockout_service(attempts, max_failures=2)
    service.record_failure(str(user.email))

    decision = _use_case(
        account_repository,
        password_hasher,
        event_outbox,
        account_lockout_service=service,
    ).execute(
        LoginUserCommand(
            email=user.email,
            plain_password=PlainPassword("StrongPass1!"),
        )
    )

    assert decision.status is AuthenticationStatus.AUTHENTICATED
    assert attempts.load_failed_attempt_counter(str(user.email)) == FailedAttemptCounter()
