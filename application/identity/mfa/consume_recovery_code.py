"""Consume a single MFA recovery code."""

from dataclasses import dataclass, field
import uuid

from application.identity.shared.ports import Clock, MfaRecoveryCodeRepository, RecoveryCodeHasher
from domain.identity.mfa import MfaPolicy
from domain.identity.verification import VerificationCode


@dataclass(frozen=True)
class ConsumeRecoveryCodeCommand:
    user_id: uuid.UUID
    code: VerificationCode = field(repr=False)


class ConsumeRecoveryCodeUseCase:
    def __init__(
        self,
        *,
        recovery_code_repository: MfaRecoveryCodeRepository,
        recovery_code_hasher: RecoveryCodeHasher,
        clock: Clock,
        mfa_policy: MfaPolicy | None = None,
    ) -> None:
        self.recovery_code_repository = recovery_code_repository
        self.recovery_code_hasher = recovery_code_hasher
        self.clock = clock
        self.mfa_policy = mfa_policy or MfaPolicy()

    def execute(self, cmd: ConsumeRecoveryCodeCommand) -> bool:
        recovery_codes = self.recovery_code_repository.get_for_user(cmd.user_id)
        if not recovery_codes:
            return False
        result = self.mfa_policy.consume_recovery_code(
            recovery_codes=recovery_codes,
            presented_code=cmd.code.value,
            hash_code=self.recovery_code_hasher.hash_recovery_code,
            now=self.clock.now(),
        )
        if result.accepted:
            self.recovery_code_repository.save_for_user(cmd.user_id, result.recovery_codes)
        return result.accepted


__all__ = ["ConsumeRecoveryCodeCommand", "ConsumeRecoveryCodeUseCase"]
