"""Command for confirming MFA enrollment."""

from dataclasses import dataclass, field
import uuid

from domain.identity.verification import VerificationCode


@dataclass(frozen=True)
class VerifyTwoFactorSetupCommand:
    user_id: uuid.UUID
    token: VerificationCode = field(repr=False)


__all__ = ["VerifyTwoFactorSetupCommand"]
