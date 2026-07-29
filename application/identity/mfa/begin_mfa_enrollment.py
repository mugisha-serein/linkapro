"""Begin TOTP MFA enrollment for an account."""

from application.identity.mfa.begin_mfa_enrollment_command import EnableTwoFactorCommand
from application.identity.dtos import TwoFactorSetupDTO
from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    MfaEnrollmentRepository,
    MfaEnrollmentState,
    TotpService,
)
from domain.identity.mfa import MfaMethod, MfaPolicy
from domain.shared.utils import utc_now


class BeginMfaEnrollmentUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        mfa_enrollment_repository: MfaEnrollmentRepository,
        totp_service: TotpService,
        mfa_policy: MfaPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.mfa_enrollment_repository = mfa_enrollment_repository
        self.totp_service = totp_service
        self.mfa_policy = mfa_policy or MfaPolicy()

    def execute(self, cmd: EnableTwoFactorCommand) -> TwoFactorSetupDTO:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        secret = self.totp_service.generate_secret()
        challenge = self.mfa_policy.issue_challenge(
            user_id=user.id,
            method=MfaMethod.TOTP,
            now=utc_now(),
        )
        provisioning_uri = self.totp_service.provisioning_uri(
            secret,
            name=user.email.value,
            issuer_name="Linkapro",
        )
        self.mfa_enrollment_repository.save(
            MfaEnrollmentState(challenge=challenge, secret=secret),
            ttl=self.mfa_policy.challenge_ttl_seconds(),
        )

        return TwoFactorSetupDTO(
            enrollment_id=str(challenge.id),
            secret=secret,
            provisioning_uri=provisioning_uri,
        )


__all__ = [
    "BeginMfaEnrollmentUseCase",
]
