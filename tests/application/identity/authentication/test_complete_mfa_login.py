import uuid
from datetime import timedelta
from unittest.mock import Mock

import pyotp

from application.identity.authentication import AuthenticationStatus, AuthenticatedSessionIssuer
from application.identity.authentication import CompleteMfaLoginUseCase
from application.identity.authentication.complete_mfa_login_command import LoginTwoFactorCommand
from application.identity.shared.dtos import MfaLoginGrant
from domain.identity.account import User, UserRole
from domain.identity.authentication import UserLoggedIn
from domain.identity.credentials import Email, PasswordHash
from domain.identity.mfa import MfaMethod, MfaPolicy, TOTPSecret
from domain.identity.verification import VerificationCode
from domain.shared.utils import utc_now


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
    mfa_challenge_repository,
    mfa_replay_store,
    totp_service,
    event_outbox,
    consume_recovery_code_use_case=None,
    session_store=None,
):
    session_store = session_store or _session_store()
    if consume_recovery_code_use_case is None:
        consume_recovery_code_use_case = Mock()
        consume_recovery_code_use_case.execute.return_value = False
    return CompleteMfaLoginUseCase(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_challenge_repository=mfa_challenge_repository,
        mfa_replay_store=mfa_replay_store,
        totp_service=totp_service,
        consume_recovery_code_use_case=consume_recovery_code_use_case,
        event_outbox=event_outbox,
        session_issuer=AuthenticatedSessionIssuer(token_service, session_store),
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
    challenge = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=1).issue_challenge(
        user_id=user.id,
        method=MfaMethod.TOTP,
        now=utc_now(),
    )
    grant = MfaLoginGrant(
        grant_id="temp-jti",
        account_id=user.id,
        expires_at=challenge.expires_at,
        challenge_id=challenge.id,
    )
    token_service = _token_service()
    token_service.inspect_mfa_login_grant.return_value = grant
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    totp_secret_repository.get_totp_secret.return_value = TOTPSecret(secret)
    token_blacklist = Mock()
    token_blacklist.is_mfa_grant_blacklisted.return_value = False
    mfa_challenge_repository = Mock()
    mfa_challenge_repository.get.return_value = challenge
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = False
    event_outbox = Mock()

    result = _use_case(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_challenge_repository=mfa_challenge_repository,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
    ).execute(LoginTwoFactorCommand(temp_token="temp", token=token))

    assert result.status is AuthenticationStatus.AUTHENTICATED
    token_blacklist.is_mfa_grant_blacklisted.assert_called_once_with(grant)
    token_blacklist.blacklist_mfa_grant.assert_called_once_with(grant)
    mfa_replay_store.has_been_used.assert_called_once_with(challenge.id, token)
    assert mfa_replay_store.mark_used.call_args.args == (challenge.id, token)
    replay_ttl = mfa_replay_store.mark_used.call_args.kwargs["ttl"]
    assert 1 <= replay_ttl <= 180
    assert mfa_challenge_repository.save.call_args.args[0].consumed_at is not None
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
    challenge = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=1).issue_challenge(
        user_id=user.id,
        method=MfaMethod.TOTP,
        now=utc_now(),
    )
    grant = MfaLoginGrant(
        grant_id="temp-jti",
        account_id=user.id,
        expires_at=challenge.expires_at,
        challenge_id=challenge.id,
    )
    token_service = _token_service()
    token_service.inspect_mfa_login_grant.return_value = grant
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    totp_secret_repository.get_totp_secret.return_value = TOTPSecret(secret)
    token_blacklist = Mock()
    token_blacklist.is_mfa_grant_blacklisted.return_value = False
    mfa_challenge_repository = Mock()
    mfa_challenge_repository.get.return_value = challenge
    mfa_replay_store = Mock()
    mfa_replay_store.has_been_used.return_value = True
    event_outbox = Mock()

    result = _use_case(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_challenge_repository=mfa_challenge_repository,
        mfa_replay_store=mfa_replay_store,
        totp_service=_totp_service(),
        event_outbox=event_outbox,
    ).execute(LoginTwoFactorCommand(temp_token="temp", token=token))

    assert result.status is AuthenticationStatus.INVALID_MFA_CODE
    mfa_replay_store.mark_used.assert_not_called()
    account_repository.save.assert_not_called()
    event_outbox.dispatch.assert_not_called()


def test_complete_mfa_login_accepts_recovery_code_when_totp_fails():
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
    token = VerificationCode("abcd-efgh")
    challenge = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=1).issue_challenge(
        user_id=user.id,
        method=MfaMethod.TOTP,
        now=utc_now(),
    )
    grant = MfaLoginGrant(
        grant_id="temp-jti",
        account_id=user.id,
        expires_at=challenge.expires_at,
        challenge_id=challenge.id,
    )
    token_service = _token_service()
    token_service.inspect_mfa_login_grant.return_value = grant
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    totp_secret_repository = Mock()
    totp_secret_repository.get_totp_secret.return_value = TOTPSecret(pyotp.random_base32())
    token_blacklist = Mock()
    token_blacklist.is_mfa_grant_blacklisted.return_value = False
    mfa_challenge_repository = Mock()
    mfa_challenge_repository.get.return_value = challenge
    mfa_replay_store = Mock()
    totp_service = Mock()
    totp_service.verify.return_value = False
    consume_recovery_code_use_case = Mock()
    consume_recovery_code_use_case.execute.return_value = True
    event_outbox = Mock()

    result = _use_case(
        account_repository=account_repository,
        totp_secret_repository=totp_secret_repository,
        token_service=token_service,
        token_blacklist=token_blacklist,
        mfa_challenge_repository=mfa_challenge_repository,
        mfa_replay_store=mfa_replay_store,
        totp_service=totp_service,
        consume_recovery_code_use_case=consume_recovery_code_use_case,
        event_outbox=event_outbox,
    ).execute(LoginTwoFactorCommand(temp_token="temp", token=token))

    assert result.status is AuthenticationStatus.AUTHENTICATED
    consume_recovery_code_use_case.execute.assert_called_once()
    mfa_replay_store.has_been_used.assert_not_called()
    mfa_replay_store.mark_used.assert_not_called()
    assert mfa_challenge_repository.save.call_args.args[0].consumed_at is not None
