"""Confirm TOTP MFA enrollment for an account."""

from application.identity.mfa.confirm_mfa_enrollment_command import VerifyTwoFactorSetupCommand
from application.identity.errors import InvalidTwoFactorCodeError, UserNotFoundError
from application.identity.shared.ports import (
    EventOutbox,
    TotpSecretRepository,
    AccountRepository,
    MfaEnrollmentRepository,
    MfaEnrollmentState,
    MfaReplayStore,
    TotpService,
    IdentityUnitOfWork,
)
from domain.identity.mfa import (
    MfaPolicy,
    TOTPSecret,
)
from domain.shared.utils import utc_now


class ConfirmMfaEnrollmentUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        totp_secret_repository: TotpSecretRepository,
        mfa_enrollment_repository: MfaEnrollmentRepository,
        mfa_replay_store: MfaReplayStore,
        totp_service: TotpService,
        event_outbox: EventOutbox,
        unit_of_work: IdentityUnitOfWork,
        mfa_policy: MfaPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.mfa_enrollment_repository = mfa_enrollment_repository
        self.mfa_replay_store = mfa_replay_store
        self.totp_service = totp_service
        self.event_outbox = event_outbox
        self.unit_of_work = unit_of_work
        self.mfa_policy = mfa_policy or MfaPolicy()

    def execute(self, cmd: VerifyTwoFactorSetupCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        setup_state = self.mfa_enrollment_repository.get(user.id)
        if not setup_state:
            raise InvalidTwoFactorCodeError("TOTP setup expired or not initiated")
        challenge = setup_state.challenge

        now = utc_now()
        result = self.mfa_policy.verify_challenge(
            challenge=challenge,
            accepted=self.totp_service.verify(TOTPSecret(setup_state.secret), cmd.token, now=now),
            now=now,
        )
        if not result.accepted:
            self.mfa_enrollment_repository.save(
                MfaEnrollmentState(challenge=result.challenge, secret=setup_state.secret),
                ttl=self.mfa_policy.remaining_challenge_ttl_seconds(
                    result.challenge,
                    now=now,
                ),
            )
            raise InvalidTwoFactorCodeError("Invalid TOTP token")
        if self.mfa_replay_store.has_been_used(challenge.id, cmd.token):
            raise InvalidTwoFactorCodeError("Invalid TOTP token")
        self.mfa_replay_store.mark_used(
            challenge.id,
            cmd.token,
            ttl=self.mfa_policy.remaining_challenge_ttl_seconds(challenge, now=now),
        )

        with self.unit_of_work as unit_of_work:
            self.totp_secret_repository.set_totp_secret(user.id, TOTPSecret(setup_state.secret))
            user.enable_two_factor()
            self.account_repository.save(user)
            for event in user.pull_events():
                self.event_outbox.dispatch(event)
            self.mfa_enrollment_repository.consume(user.id)
            unit_of_work.commit()


__all__ = ["ConfirmMfaEnrollmentUseCase"]
