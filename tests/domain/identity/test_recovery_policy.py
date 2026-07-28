from datetime import timedelta
import uuid

import pytest

from domain.identity.recovery import (
    InvalidPasswordResetToken,
    PasswordResetPolicy,
    PasswordResetToken,
    PasswordResetTokenStatus,
    PasswordResetUserInactive,
)
from domain.identity.shared import SystemClock


def _token(*, status=PasswordResetTokenStatus.ACTIVE, expires_delta=timedelta(minutes=5)):
    now = SystemClock().now()
    return PasswordResetToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        jti=str(uuid.uuid4()),
        token_hash="h" * 64,
        status=status,
        expires_at=now + expires_delta,
    )


def test_password_reset_policy_consumes_active_token():
    now = SystemClock().now()
    policy = PasswordResetPolicy()

    used = policy.consume_token(
        _token(),
        now=now,
        used_ip_hash="ip-hash",
        used_user_agent_hash="ua-hash",
    )

    assert used.status is PasswordResetTokenStatus.USED
    assert used.used_at == now
    assert used.used_ip_hash == "ip-hash"
    assert used.used_user_agent_hash == "ua-hash"


def test_password_reset_policy_rejects_inactive_token_status():
    with pytest.raises(InvalidPasswordResetToken):
        PasswordResetPolicy().ensure_token_can_be_used(
            _token(status=PasswordResetTokenStatus.USED),
            now=SystemClock().now(),
        )


def test_password_reset_policy_rejects_expired_token():
    with pytest.raises(InvalidPasswordResetToken):
        PasswordResetPolicy().ensure_token_can_be_used(
            _token(expires_delta=timedelta(seconds=-1)),
            now=SystemClock().now(),
        )


def test_password_reset_policy_rejects_inactive_user():
    with pytest.raises(PasswordResetUserInactive):
        PasswordResetPolicy().ensure_user_can_reset_password(user_is_active=False)
