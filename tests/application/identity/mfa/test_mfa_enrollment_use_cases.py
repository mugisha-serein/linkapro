import uuid
from datetime import UTC, datetime
from unittest.mock import ANY, Mock

import pytest
import pyotp

from application.identity.commands import DisableMfaCommand, EnableTwoFactorCommand, VerifyTwoFactorSetupCommand
from application.identity.errors import InvalidTwoFactorCodeError
from application.identity.mfa import (
    BeginMfaEnrollmentUseCase,
    ConfirmMfaEnrollmentUseCase,
    DisableMfaUseCase,
)
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.mfa import UserTwoFactorDisabled, UserTwoFactorEnabled
from domain.identity.verification import VerificationCode


class FixedClock:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=UTC)


def _user(*, two_factor_enabled=False):
    return User(
        id=uuid.uuid4(),
        email=Email("mfa@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="MFA",
        last_name="User",
        role=UserRole.PLANNER,
        two_factor_enabled=two_factor_enabled,
    )


def _totp_service(secret: str | None = None):
    service = Mock()
    service.generate_secret.return_value = secret or pyotp.random_base32()
    service.provisioning_uri.side_effect = (
        lambda generated_secret, *, name, issuer_name: pyotp.TOTP(generated_secret).provisioning_uri(
            name=name,
            issuer_name=issuer_name,
        )
    )
    service.verify.side_effect = (
        lambda totp_secret, token, *, now: pyotp.TOTP(
            totp_secret.reveal_for_totp_verification()
        ).verify(token.value, for_time=now)
    )
    return service


def test_begin_mfa_enrollment_stores_challenge_state_and_returns_setup_dto():
    user = _user()
    secret = pyotp.random_base32()
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    mfa_enrollment_store = Mock()

    result = BeginMfaEnrollmentUseCase(
        account_repository=account_repository,
        mfa_enrollment_store=mfa_enrollment_store,
        totp_service=_totp_service(secret),
    ).execute(EnableTwoFactorCommand(user_id=user.id))

    assert result.secret == secret
    assert result.enrollment_id
    mfa_enrollment_store.save.assert_called_once()
    assert mfa_enrollment_store.save.call_args.args[0] == user.id
    assert mfa_enrollment_store.save.call_args.kwargs["ttl"] == 600


def test_confirm_mfa_enrollment_enables_user_and_consumes_setup():
    user = _user()
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    mfa_enrollment_store = Mock()
    mfa_enrollment_store.get.return_value = secret
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = False
    event_outbox = Mock()

    ConfirmMfaEnrollmentUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        mfa_enrollment_store=mfa_enrollment_store,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
    ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    assert user.two_factor_enabled is True
    totp_secret_repository.set_totp_secret.assert_called_once()
    mfa_replay_store.has_been_used.assert_called_once_with(ANY, token)
    mfa_replay_store.mark_used.assert_called_once_with(ANY, token, ttl=90)
    mfa_enrollment_store.consume.assert_called_once_with(user.id)
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserTwoFactorEnabled)


def test_confirm_mfa_enrollment_rejects_replayed_token():
    user = _user()
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    mfa_enrollment_store = Mock()
    mfa_enrollment_store.get.return_value = secret
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = True
    event_outbox = Mock()

    with pytest.raises(InvalidTwoFactorCodeError, match="Invalid TOTP token"):
        ConfirmMfaEnrollmentUseCase(
            account_repository=account_repository,
            totp_secret_repository=Mock(),
            mfa_enrollment_store=mfa_enrollment_store,
            mfa_replay_store=mfa_replay_store,
            totp_service=_totp_service(),
            event_outbox=event_outbox,
        ).execute(VerifyTwoFactorSetupCommand(user_id=user.id, token=token))

    mfa_replay_store.mark_used.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_disable_mfa_clears_secret_and_records_event():
    user = _user(two_factor_enabled=True)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    event_outbox = Mock()

    DisableMfaUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        event_outbox=event_outbox,
        clock=FixedClock(),
    ).execute(DisableMfaCommand(user_id=user.id))

    assert user.two_factor_enabled is False
    totp_secret_repository.clear_totp_secret.assert_called_once_with(user.id)
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserTwoFactorDisabled)
    assert event.occurred_at == datetime(2026, 1, 1, tzinfo=UTC)
