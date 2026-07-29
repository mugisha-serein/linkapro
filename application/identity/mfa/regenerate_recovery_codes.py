"""Regenerate MFA recovery codes for an account."""

from dataclasses import dataclass
import uuid

from application.identity.mfa.generate_recovery_codes import (
    GenerateRecoveryCodesCommand,
    GenerateRecoveryCodesUseCase,
)
from application.identity.shared.ports import MfaRecoveryCodeRepository


@dataclass(frozen=True)
class RegenerateRecoveryCodesCommand:
    user_id: uuid.UUID
    count: int = 10


class RegenerateRecoveryCodesUseCase:
    def __init__(
        self,
        *,
        recovery_code_repository: MfaRecoveryCodeRepository,
        generate_recovery_codes_use_case: GenerateRecoveryCodesUseCase,
    ) -> None:
        self.recovery_code_repository = recovery_code_repository
        self.generate_recovery_codes_use_case = generate_recovery_codes_use_case

    def execute(self, cmd: RegenerateRecoveryCodesCommand) -> tuple[str, ...]:
        self.recovery_code_repository.clear_for_user(cmd.user_id)
        return self.generate_recovery_codes_use_case.execute(
            GenerateRecoveryCodesCommand(user_id=cmd.user_id, count=cmd.count)
        )


__all__ = ["RegenerateRecoveryCodesCommand", "RegenerateRecoveryCodesUseCase"]
