import uuid
from unittest.mock import Mock

from application.identity.auth_policy import AuthenticationStatus, IdentityAuthenticationPolicy
from application.identity.authentication import LoginWithPasswordUseCase
from application.identity.commands import LoginUserCommand
from domain.identity.account import User, UserRole
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


def _use_case(account_repository, password_hasher, event_outbox, token_service=None, session_store=None):
    token_service = token_service or _token_service()
    session_store = session_store or _session_store()
    return LoginWithPasswordUseCase(
        account_repository=account_repository,
        password_hasher=password_hasher,
        auth_policy=IdentityAuthenticationPolicy(token_service, session_store),
        event_outbox=event_outbox,
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

    assert decision.status is AuthenticationStatus.INVALID_CREDENTIALS
    password_hasher.verify_against_dummy.assert_called_once_with(cmd.plain_password)
    password_hasher.verify.assert_not_called()
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


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
