"""MFA recovery-code repository port."""

from typing import Protocol
import uuid

from domain.identity.mfa import RecoveryCode


class MfaRecoveryCodeRepository(Protocol):
    def get_for_user(self, user_id: uuid.UUID) -> tuple[RecoveryCode, ...]:
        ...

    def save_for_user(self, user_id: uuid.UUID, recovery_codes: tuple[RecoveryCode, ...]) -> None:
        ...

    def replace_for_user(self, user_id: uuid.UUID, recovery_codes: tuple[RecoveryCode, ...]) -> None:
        ...

    def clear_for_user(self, user_id: uuid.UUID) -> None:
        ...


__all__ = ["MfaRecoveryCodeRepository"]
