from datetime import timedelta
import uuid

import pytest

from application.identity.commands import ResetPasswordCommand
from application.identity.recovery import (
    PasswordResetVerification,
    ResetPasswordCommandHandler,
)
from domain.identity.credentials import (
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
from domain.identity.shared import SystemClock


class FakeGateway:
    def __init__(self, *, verification=None, user=None):
        self.verification = verification
        self.user = user
        self.persisted_token = None
        self.revoked = False
        self.dispatched = []
        self.expired_token = None

    def complete_in_transaction(self, operation):
        return operation()

    def verify_reset_token(self, raw_token):
        return self.verification

    def mark_token_expired(self, token, *, now):
        self.expired_token = token

    def get_active_user_for_update(self, user_id):
        return self.user

    def get_password_history(self, user):
        return user.get("password_history", PasswordHistory())

    def password_matches(self, plain_password, password_hash):
        return password_hash.reveal_for_password_verification() == f"hash:{plain_password.value}"

    def set_user_password(self, user, new_password):
        user["password"] = new_password
        return PasswordHash(f"hash:{new_password}")

    def remember_password_hash(self, *, user, password_hash, now):
        user["password_history"] = user.get("password_history", PasswordHistory()).record(
            password_hash,
            changed_at=now,
        )

    def persist_used_token(self, token):
        self.persisted_token = token

    def revoke_other_active_tokens(self, *, user, exclude_token_id, now):
        self.revoked = True

    def dispatch_password_changed(self, event):
        self.dispatched.append(event)

    def hash_reset_value(self, value):
        return f"hash:{value}"


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


def test_reset_password_handler_changes_password_marks_token_and_dispatches_event():
    token = _token()
    user = {"id": token.user_id}
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    result = ResetPasswordCommandHandler(gateway=gateway).handle(
        ResetPasswordCommand(
            token="raw-token",
            new_password="NewValidPass1!",
            client_ip="127.0.0.1",
            user_agent="agent",
        )
    )

    assert result.user_id == token.user_id
    assert user["password"] == "NewValidPass1!"
    assert gateway.persisted_token.status is PasswordResetTokenStatus.USED
    assert gateway.persisted_token.used_ip_hash == "hash:127.0.0.1"
    assert gateway.persisted_token.used_user_agent_hash == "hash:agent"
    assert gateway.revoked is True
    assert isinstance(gateway.dispatched[0], UserPasswordChanged)


def test_reset_password_handler_rejects_missing_verification():
    gateway = FakeGateway(verification=None, user={"id": uuid.uuid4()})

    with pytest.raises(InvalidPasswordResetToken):
        ResetPasswordCommandHandler(gateway=gateway).handle(
            ResetPasswordCommand(
                token="bad",
                new_password="NewValidPass1!",
                client_ip="127.0.0.1",
                user_agent="agent",
            )
        )


def test_reset_password_handler_marks_expired_token():
    token = _token(expires_delta=timedelta(seconds=-1))
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user={"id": token.user_id},
    )

    with pytest.raises(InvalidPasswordResetToken):
        ResetPasswordCommandHandler(gateway=gateway).handle(
            ResetPasswordCommand(
                token="expired",
                new_password="NewValidPass1!",
                client_ip="127.0.0.1",
                user_agent="agent",
            )
        )

    assert gateway.expired_token == token


def test_reset_password_handler_rejects_recently_used_password():
    token = _token()
    user = {
        "id": token.user_id,
        "password_history": PasswordHistory([PasswordHash("hash:OldValidPass1!")]),
    }
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    with pytest.raises(PasswordReuseNotAllowed):
        ResetPasswordCommandHandler(gateway=gateway).handle(
            ResetPasswordCommand(
                token="raw-token",
                new_password="OldValidPass1!",
                client_ip="127.0.0.1",
                user_agent="agent",
            )
        )

    assert "password" not in user
    assert gateway.persisted_token is None


def test_reset_password_handler_rejects_weak_password():
    token = _token()
    user = {"id": token.user_id}
    gateway = FakeGateway(
        verification=PasswordResetVerification(user_id=token.user_id, token=token),
        user=user,
    )

    with pytest.raises(WeakPasswordError):
        ResetPasswordCommandHandler(gateway=gateway).handle(
            ResetPasswordCommand(
                token="raw-token",
                new_password="weakpass",
                client_ip="127.0.0.1",
                user_agent="agent",
            )
        )

    assert "password" not in user
    assert gateway.persisted_token is None
