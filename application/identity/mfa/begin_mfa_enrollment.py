"""Begin TOTP MFA enrollment for an account."""

import uuid
from datetime import datetime, timedelta

from application.identity.commands import EnableTwoFactorCommand
from application.identity.dtos import TwoFactorSetupDTO
from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import IUserRepository, MfaEnrollmentStore, TotpService
from domain.identity.mfa import MfaChallenge, MfaMethod, MfaPolicy
from domain.shared.utils import utc_now


MFA_SETUP_CHALLENGE_TTL_SECONDS = 600
MFA_SETUP_CHALLENGE_MAX_ATTEMPTS = 5


def mfa_challenge_state(challenge: MfaChallenge, secret: str | None = None) -> dict:
    state = {
        "id": str(challenge.id),
        "user_id": str(challenge.user_id),
        "method": challenge.method.value,
        "issued_at": challenge.issued_at.isoformat(),
        "expires_at": challenge.expires_at.isoformat(),
        "max_attempts": challenge.max_attempts,
        "attempt_count": challenge.attempt_count,
        "consumed_at": challenge.consumed_at.isoformat() if challenge.consumed_at else None,
    }
    if secret is not None:
        state["secret"] = secret
    return state


def mfa_challenge_from_state(
    state,
    *,
    user_id: uuid.UUID,
    ttl_seconds: int,
    max_attempts: int,
) -> MfaChallenge | None:
    now = utc_now()
    if isinstance(state, str):
        return MfaChallenge(
            id=uuid.uuid4(),
            user_id=user_id,
            method=MfaMethod.TOTP,
            issued_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(seconds=ttl_seconds),
            max_attempts=max_attempts,
        )
    if not isinstance(state, dict):
        return None
    try:
        return MfaChallenge(
            id=uuid.UUID(str(state["id"])),
            user_id=uuid.UUID(str(state["user_id"])),
            method=MfaMethod(str(state["method"])),
            issued_at=datetime.fromisoformat(str(state["issued_at"])),
            expires_at=datetime.fromisoformat(str(state["expires_at"])),
            max_attempts=int(state["max_attempts"]),
            attempt_count=int(state.get("attempt_count", 0)),
            consumed_at=(
                datetime.fromisoformat(str(state["consumed_at"]))
                if state.get("consumed_at")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def secret_from_setup_state(state) -> str | None:
    if isinstance(state, str):
        return state
    if isinstance(state, dict):
        secret = state.get("secret")
        return str(secret) if secret else None
    return None


class BeginMfaEnrollmentUseCase:
    def __init__(
        self,
        *,
        account_repository: IUserRepository,
        mfa_enrollment_store: MfaEnrollmentStore,
        totp_service: TotpService,
    ) -> None:
        self.account_repository = account_repository
        self.mfa_enrollment_store = mfa_enrollment_store
        self.totp_service = totp_service

    def execute(self, cmd: EnableTwoFactorCommand) -> TwoFactorSetupDTO:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        secret = self.totp_service.generate_secret()
        challenge = MfaPolicy(
            challenge_ttl=timedelta(seconds=MFA_SETUP_CHALLENGE_TTL_SECONDS),
            max_attempts=MFA_SETUP_CHALLENGE_MAX_ATTEMPTS,
        ).issue_challenge(
            user_id=user.id,
            method=MfaMethod.TOTP,
            now=utc_now(),
        )
        provisioning_uri = self.totp_service.provisioning_uri(
            secret,
            name=user.email.value,
            issuer_name="Linkapro",
        )
        self.mfa_enrollment_store.save(
            user.id,
            mfa_challenge_state(challenge, secret=secret),
            ttl=MFA_SETUP_CHALLENGE_TTL_SECONDS,
        )

        return TwoFactorSetupDTO(
            enrollment_id=str(challenge.id),
            secret=secret,
            provisioning_uri=provisioning_uri,
        )


__all__ = [
    "BeginMfaEnrollmentUseCase",
    "MFA_SETUP_CHALLENGE_MAX_ATTEMPTS",
    "MFA_SETUP_CHALLENGE_TTL_SECONDS",
    "mfa_challenge_from_state",
    "mfa_challenge_state",
    "secret_from_setup_state",
]
