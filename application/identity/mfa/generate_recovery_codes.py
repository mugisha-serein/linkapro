"""Generate MFA recovery codes for an account."""

from dataclasses import dataclass
import uuid

from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import (
    AccountRepository,
    IdGenerator,
    MfaRecoveryCodeRepository,
    RecoveryCodeGenerator,
    RecoveryCodeHasher,
)
from domain.identity.mfa import RecoveryCode


@dataclass(frozen=True)
class GenerateRecoveryCodesCommand:
    user_id: uuid.UUID
    count: int = 10


class GenerateRecoveryCodesUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        recovery_code_repository: MfaRecoveryCodeRepository,
        recovery_code_generator: RecoveryCodeGenerator,
        recovery_code_hasher: RecoveryCodeHasher,
        id_generator: IdGenerator,
    ) -> None:
        self.account_repository = account_repository
        self.recovery_code_repository = recovery_code_repository
        self.recovery_code_generator = recovery_code_generator
        self.recovery_code_hasher = recovery_code_hasher
        self.id_generator = id_generator

    def execute(self, cmd: GenerateRecoveryCodesCommand) -> tuple[str, ...]:
        if cmd.count <= 0:
            raise ValueError("Recovery code count must be positive")
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        plaintext_codes = tuple(self.recovery_code_generator.generate() for _ in range(cmd.count))
        recovery_codes = tuple(
            RecoveryCode(
                id=self.id_generator.new_id(),
                code_hash=self.recovery_code_hasher.hash_recovery_code(code),
            )
            for code in plaintext_codes
        )
        self.recovery_code_repository.replace_for_user(user.id, recovery_codes)
        return plaintext_codes


__all__ = ["GenerateRecoveryCodesCommand", "GenerateRecoveryCodesUseCase"]
