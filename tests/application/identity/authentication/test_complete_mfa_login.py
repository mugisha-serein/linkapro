import uuid
from unittest.mock import Mock

import pyotp

from application.identity.auth_policy import AuthenticationStatus, IdentityAuthenticationPolicy
from application.identity.authentication import CompleteMfaLoginUseCase
from application.identity.commands import LoginTwoFactorCommand
from domain.identity.account import User, UserRole
from domain.identity.authentication import UserLoggedIn
from domain.identity.credentials import Email, PasswordHash
from domain.identity.mfa import TOTPSecret
from domain.identity.verification import VerificationCode


def _token_service():
    service = Mock()
    service.create_access_token.return_value = "access-token"
    service.create_refresh_token.return_value = "refresh-token"
    return service


def _session_store():
    store = Mock()
    store.create_identity_session.return_value = "session-id"
    return store


def _totp_service():
    service = Mock()
    service.verify.side_effect = (
        lambda secret, token, *, now: pyotp.TOTP(secret.reveal_for_totp_verification()).verify(
            token.value,
            for_time=now,
        )
    )
    return service


def _use_case(
    *,
    account_repository,
    totp_secret_repository,
    token_service,
    token_blacklist,
    mfa_replay_store,
    totp_service,
    event_outbox,
    session_store=None,
):
    session_store = session_store or _session_store()
    return CompleteMfaLoginUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_replay_store=mfa_replay_store,
        totp_service=totp_service,
        auth_policy=IdentityAuthenticationPolicy(token_service, session_store),
        event_outbox=event_outbox,
    )


def test_complete_mfa_login_blacklists_consumed_temp_token():
    user = User(
        id=uuid.uuid4(),
        email=Email("mfa-login@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="MFA",
        last_name="Login",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    token_service = _token_service()
    token_service.verify_temp_token.return_value = {
        "user_id": str(user.id),
        "jti": "temp-jti",
    }
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    totp_secret_repository.get_totp_secret.return_value = TOTPSecret(secret)
    token_blacklist = Mock()
    token_blacklist.is_blacklisted.return_value = False
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = False
    event_outbox = Mock()

    result = _use_case(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
    ).execute(LoginTwoFactorCommand(temp_token="temp", token=token))

    assert result.status is AuthenticationStatus.AUTHENTICATED
    token_blacklist.is_blacklisted.assert_called_once_with("temp-jti")
    token_blacklist.blacklist.assert_called_once_with("temp-jti", ttl=180)
    expected_challenge_id = uuid.uuid5(uuid.NAMESPACE_URL, "temp-jti")
    mfa_replay_store.has_been_used.assert_called_once_with(expected_challenge_id, token)
    mfa_replay_store.mark_used.assert_called_once_with(expected_challenge_id, token, ttl=90)
    account_repository.save.assert_called_once_with(user)
    event = event_outbox.dispatch.call_args.args[0]
    assert isinstance(event, UserLoggedIn)


def test_complete_mfa_login_rejects_replayed_totp_token():
    user = User(
        id=uuid.uuid4(),
        email=Email("mfa-login@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="MFA",
        last_name="Login",
        role=UserRole.PLANNER,
        is_active=True,
        is_verified=True,
    )
    secret = pyotp.random_base32()
    token = VerificationCode(pyotp.TOTP(secret).now())
    token_service = _token_service()
    token_service.verify_temp_token.return_value = {"user_id": str(user.id)}
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    totp_secret_repository.get_totp_secret.return_value = TOTPSecret(secret)
    token_blacklist = Mock()
    token_blacklist.is_blacklisted.return_value = False
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = True
    event_outbox = Mock()

    result = _use_case(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
    ).execute(LoginTwoFactorCommand(temp_token="temp", token=token))

    assert result.status is AuthenticationStatus.INVALID_MFA_CODE
    mfa_replay_store.mark_used.assert_not_called()
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()
