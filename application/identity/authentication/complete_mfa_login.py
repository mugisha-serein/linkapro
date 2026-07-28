"""Complete a password login that requires MFA."""

import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from application.identity.auth_policy import AuthenticationDecision, AuthenticationStatus, IdentityAuthenticationPolicy
from application.identity.commands import LoginTwoFactorCommand
from application.identity.shared.ports import (
    ITOTPSecretRepository,
    ITokenBlacklist,
    IUserRepository,
    MfaReplayStore,
    TotpService,
)
from domain.identity.mfa import MfaChallenge, MfaChallengeExpired, MfaMethod, MfaVerificationResult
from domain.shared.utils import utc_now


TOTP_REPLAY_TTL_SECONDS = 90


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


def _temp_token_blacklist_key(payload: dict, temp_token: str) -> str:
    jti = payload.get("jti")
    if jti:
        return str(jti)
    token_hash = hashlib.sha256(temp_token.encode("utf-8")).hexdigest()
    return f"temp:{token_hash}"


def _temp_token_blacklist_ttl(payload: dict) -> int:
    exp = payload.get("exp")
    if exp is None:
        return 180
    return max(int(float(exp) - time.time()), 1)


def _verify_totp_challenge(
    *,
    challenge: MfaChallenge,
    accepted: bool,
    now: datetime,
) -> MfaVerificationResult:
    try:
        can_attempt = challenge.can_attempt(now=now)
    except MfaChallengeExpired:
        return MfaVerificationResult(False, challenge)
    if challenge.method is not MfaMethod.TOTP or not can_attempt:
        return MfaVerificationResult(False, challenge)
    if accepted:
        return MfaVerificationResult(True, challenge.consume(now=now))
    return MfaVerificationResult(False, challenge.record_failed_attempt())


def _mfa_challenge_from_temp_payload(payload: dict, *, user_id: uuid.UUID) -> MfaChallenge:
    now = utc_now()
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(float(exp), tz=UTC) if exp is not None else now + timedelta(seconds=180)
    if expires_at <= now:
        expires_at = now + timedelta(seconds=1)
    return MfaChallenge(
        id=uuid.uuid5(uuid.NAMESPACE_URL, str(payload.get("jti") or f"mfa-temp:{user_id}")),
        user_id=user_id,
        method=MfaMethod.TOTP,
        issued_at=now - timedelta(seconds=1),
        expires_at=expires_at,
        max_attempts=1,
    )


class CompleteMfaLoginUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        totp_secret_repository: ITOTPSecretRepository,
        token_service,
        token_blacklist: ITokenBlacklist,
        mfa_replay_store: MfaReplayStore,
        totp_service: TotpService,
        auth_policy: IdentityAuthenticationPolicy,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.token_service = token_service
        self.token_blacklist = token_blacklist
        self.mfa_replay_store = mfa_replay_store
        self.totp_service = totp_service
        self.auth_policy = auth_policy
        self.event_outbox = event_outbox

    def execute(self, cmd: LoginTwoFactorCommand) -> AuthenticationDecision:
        payload = self.token_service.verify_temp_token(cmd.temp_token)
        if not payload:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        temp_token_key = _temp_token_blacklist_key(payload, cmd.temp_token)
        if self.token_blacklist.is_blacklisted(temp_token_key):
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        user_id = uuid.UUID(payload["user_id"])
        user = self.account_repository.get_by_id(user_id)
        if not user or not user.is_active:
            return AuthenticationDecision(
                status=AuthenticationStatus.INACTIVE
                if user and not user.is_active
                else AuthenticationStatus.INVALID_TEMP_TOKEN
            )

        secret = self.totp_secret_repository.get_totp_secret(user.id)
        if not secret:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        challenge = _mfa_challenge_from_temp_payload(payload, user_id=user.id)
        now = utc_now()
        result = _verify_totp_challenge(
            challenge=challenge,
            accepted=self.totp_service.verify(secret, cmd.token, now=now),
            now=now,
        )
        if not result.accepted:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_MFA_CODE)
        if self.mfa_replay_store.has_been_used(challenge.id, cmd.token):
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_MFA_CODE)
        self.mfa_replay_store.mark_used(challenge.id, cmd.token, ttl=TOTP_REPLAY_TTL_SECONDS)

        user.record_login()
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)

        decision = self.auth_policy.issue_authenticated_login(user)
        self.token_blacklist.blacklist(temp_token_key, ttl=_temp_token_blacklist_ttl(payload))
        return decision


__all__ = ["CompleteMfaLoginUseCase"]
