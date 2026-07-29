"""Command for beginning MFA enrollment."""

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class EnableTwoFactorCommand:
    user_id: uuid.UUID


__all__ = ["EnableTwoFactorCommand"]
