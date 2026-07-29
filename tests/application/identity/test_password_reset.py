from datetime import timedelta
import uuid

import pytest

from application.identity.recovery.reset_password_command import (
    PasswordResetTokenInput,
    ResetPasswordCommand,
    SecurityMetadataHash,
)
from application.identity.recovery.reset_password import (
    PasswordResetVerification,
    ResetPasswordCommandHandler,
)
from domain.identity.credentials import (
    Email,
    PasswordHash,
    PasswordHistory,
    PasswordReuseNotAllowed,
    PlainPassword,
    UserPasswordChanged,
    WeakPasswordError,
)
from domain.identity.recovery import (
    InvalidPasswordResetToken,
    PasswordResetToken,
    PasswordResetTokenStatus,
)
from domain.identity.account import User, UserRole
from domain.identity.shared import SystemClock


class FakeGateway:
    def __init__(self, *, verification=None, user=None):
        self.verification = verification
        self.user = user
        self.persisted_token = None
        self.revoked = False
        self.dispatched = []
        self.expired_token = None

    def verify_reset_token(self, raw_token):
        return self.verification

    def mark_token_expired(self, token, *, now):
        self.expired_token = token

    def get_active_user_for_update(self, user_id):
        return self.user

    def get_password_history(self, user):
        return getattr(user, "password_history", PasswordHistory())

    def verify(self, plain_password, password_hash):
        return password_hash.reveal_for_password_verification() == f"hash:{plain_password.value}"

    def hash(self, plain_password):
        return f"hash:{plain_password.value}"

    def remember_password_hash(self, *, user, password_hash, now):
        user.password_history = getattr(user, "password_history", PasswordHistory()).record(
            password_hash,
            changed_at=now,
        )

    def persist_used_token(self, token):
        self.persisted_token = token

    def revoke_other_active_tokens(self, *, user, exclude_token_id, now):
        self.revoked = True

    def dispatch(self, event):
        self.dispatched.append(event)


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
        self.committed = False
        self.rolled_back = True


class FakeEventOutbox:
    def __init__(self):
        self.dispatched = []

    def dispatch(self, event):
        self.dispatched.append(event)


class FakeRevokeAllSessionsUseCase:
    def __init__(self):
        self.calls = []

    def execute(self, *, user_id, reason="all_sessions_revoked"):
        self.calls.append({"user_id": user_id, "reason": reason})


class FakeAccountRepository:
    def __init__(self, user=None):
        self.user = user
        self.saved = []

    def get_by_id(self, user_id):
        if self.user and self.user.id == user_id:
            return self.user
        return None

    def save(self, user):
        self.saved.append(user)
        return user


def _handler(
    gateway,
    *,
    account_repository=None,
    event_outbox=None,
    revoke_all_sessions_use_case=None,
    unit_of_work=None,
):
    return ResetPasswordCommandHandler(
        account_repository=account_repository or FakeAccountRepository(gateway.user),
        password_reset_repository=gateway,
        password_history_repository=gateway,
        password_hasher=gateway,
        event_outbox=event_outbox or gateway,
        revoke_all_sessions_use_case=revoke_all_sessions_use_case or FakeRevokeAllSessionsUseCase(),
        unit_of_work=unit_of_work or RecordingUnitOfWork(),
    )


def _token(*, expires_delta=timedelta(minutes=5)):
    now = SystemClock().now()
    return PasswordResetToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        jti=str(uuid.uuid4()),
        token_hash="h" * 64,
        status=PasswordResetTokenStatus.ACTIVE,
        expires_at=now + expires_delta,
    )


def _user(user_id=None, *, password_hash="hash:OldValidPass1!", is_active=True):
    return User(
        id=user_id or uuid.uuid4(),
        email=Email("reset@example.com"),
        password_hash=PasswordHash(password_hash),
        first_name="Reset",
        last_name="User",
        role=UserRole.PLANNER,
        is_active=is_active,
        is_verified=True,
    )


def _reset_command(*, token="raw-token", new_password="NewValidPass1!"):
    return ResetPasswordCommand(
        token=PasswordResetTokenInput(token),
        new_password=PlainPassword(new_password),
        client_ip_hash=SecurityMetadataHash("a" * 64),
        user_agent_hash=SecurityMetadataHash("b" * 64),
    )


def test_reset_password_handler_changes_password_marks_token_and_dispatches_event():
    token = _token()
    user = _user(token.user_id)
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    unit_of_work = RecordingUnitOfWork()
    account_repository = FakeAccountRepository(user)
    revoke_all_sessions_use_case = FakeRevokeAllSessionsUseCase()
    previous_auth_token_version = user.auth_token_version

    result = _handler(
        gateway,
        account_repository=account_repository,
        revoke_all_sessions_use_case=revoke_all_sessions_use_case,
        unit_of_work=unit_of_work,
    ).handle(
        _reset_command()
    )

    assert result.user_id == token.user_id
    assert user.password_hash == PasswordHash("hash:NewValidPass1!")
    assert user.auth_token_version == previous_auth_token_version + 1
    assert account_repository.saved == [user]
    assert gateway.persisted_token.status is PasswordResetTokenStatus.USED
    assert gateway.persisted_token.used_ip_hash == "a" * 64
    assert gateway.persisted_token.used_user_agent_hash == "b" * 64
    assert gateway.revoked is True
    assert isinstance(gateway.dispatched[0], UserPasswordChanged)
    assert revoke_all_sessions_use_case.calls == [
        {"user_id": token.user_id, "reason": "password_reset"}
    ]
    assert unit_of_work.entered is True
    assert unit_of_work.committed is True
    assert unit_of_work.rolled_back is False


def test_reset_password_handler_rolls_back_unit_of_work_when_outbox_dispatch_fails():
    token = _token()
    user = _user(token.user_id)
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )
    event_outbox = FakeEventOutbox()
    unit_of_work = RecordingUnitOfWork()

    def unavailable(event):
        raise RuntimeError("outbox unavailable")

    event_outbox.dispatch = unavailable

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        _handler(
            gateway,
            event_outbox=event_outbox,
            unit_of_work=unit_of_work,
        ).handle(
            _reset_command()
        )

    assert unit_of_work.entered is True
    assert unit_of_work.committed is False
    assert unit_of_work.rolled_back is True


def test_reset_password_handler_rejects_missing_verification():
    gateway = FakeGateway(verification=None, user=_user())

    with pytest.raises(InvalidPasswordResetToken):
        _handler(gateway).handle(
            _reset_command(token="bad")
        )


def test_reset_password_handler_marks_expired_token():
    token = _token(expires_delta=timedelta(seconds=-1))
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=_user(token.user_id),
    )

    with pytest.raises(InvalidPasswordResetToken):
        _handler(gateway).handle(
            _reset_command(token="expired")
        )

    assert gateway.expired_token == token


def test_reset_password_handler_rejects_recently_used_password():
    token = _token()
    user = _user(token.user_id)
    user.password_history = PasswordHistory([PasswordHash("hash:OldValidPass1!")])
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    with pytest.raises(PasswordReuseNotAllowed):
        _handler(gateway).handle(
            _reset_command(new_password="OldValidPass1!")
        )

    assert user.password_hash == PasswordHash("hash:OldValidPass1!")
    assert gateway.persisted_token is None


def test_reset_password_handler_rejects_weak_password():
    token = _token()
    user = _user(token.user_id)
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    with pytest.raises(WeakPasswordError):
        _handler(gateway).handle(
            _reset_command(new_password="weakpass")
        )

    assert user.password_hash == PasswordHash("hash:OldValidPass1!")
    assert gateway.persisted_token is None
