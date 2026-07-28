"""Confirm TOTP MFA enrollment for an account."""

from datetime import datetime
from typing import Protocol

from application.identity.commands import VerifyTwoFactorSetupCommand
from application.identity.errors import InvalidTwoFactorCodeError, UserNotFoundError
from application.identity.shared.ports import (
    ITOTPSecretRepository,
    IUserRepository,
    MfaEnrollmentStore,
    MfaReplayStore,
    TotpService,
)
from domain.identity.mfa import MfaChallenge, MfaChallengeExpired, MfaMethod, MfaVerificationResult, TOTPSecret
from domain.shared.utils import utc_now

from .begin_mfa_enrollment import (
    MFA_SETUP_CHALLENGE_MAX_ATTEMPTS,
    MFA_SETUP_CHALLENGE_TTL_SECONDS,
    mfa_challenge_from_state,
    mfa_challenge_state,
    secret_from_setup_state,
)


TOTP_REPLAY_TTL_SECONDS = 90


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


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


class ConfirmMfaEnrollmentUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        totp_secret_repository: ITOTPSecretRepository,
        mfa_enrollment_store: MfaEnrollmentStore,
        mfa_replay_store: MfaReplayStore,
        totp_service: TotpService,
        event_outbox: EventOutbox,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.mfa_enrollment_store = mfa_enrollment_store
        self.mfa_replay_store = mfa_replay_store
        self.totp_service = totp_service
        self.event_outbox = event_outbox

    def execute(self, cmd: VerifyTwoFactorSetupCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        setup_state = self.mfa_enrollment_store.get(user.id)
        secret = secret_from_setup_state(setup_state)
        if not secret:
            raise InvalidTwoFactorCodeError("TOTP setup expired or not initiated")
        challenge = mfa_challenge_from_state(
            setup_state,
            user_id=user.id,
            ttl_seconds=MFA_SETUP_CHALLENGE_TTL_SECONDS,
            max_attempts=MFA_SETUP_CHALLENGE_MAX_ATTEMPTS,
        )
        if not challenge:
            raise InvalidTwoFactorCodeError("TOTP setup expired or not initiated")

        now = utc_now()
        result = _verify_totp_challenge(
            challenge=challenge,
            accepted=self.totp_service.verify(TOTPSecret(secret), cmd.token, now=now),
            now=now,
        )
        if not result.accepted:
            if not isinstance(setup_state, str):
                self.mfa_enrollment_store.save(
                    user.id,
                    mfa_challenge_state(result.challenge, secret=secret),
                    ttl=MFA_SETUP_CHALLENGE_TTL_SECONDS,
                )
            raise InvalidTwoFactorCodeError("Invalid TOTP token")
        if self.mfa_replay_store.has_been_used(challenge.id, cmd.token):
            raise InvalidTwoFactorCodeError("Invalid TOTP token")
        self.mfa_replay_store.mark_used(challenge.id, cmd.token, ttl=TOTP_REPLAY_TTL_SECONDS)

        self.totp_secret_repository.set_totp_secret(user.id, TOTPSecret(secret))
        user.enable_two_factor()
        self.account_repository.save(user)
        self.mfa_enrollment_store.consume(user.id)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)


__all__ = ["ConfirmMfaEnrollmentUseCase"]
