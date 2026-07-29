"""Command for disabling MFA."""

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class DisableMfaCommand:
    user_id: uuid.UUID


__all__ = ["DisableMfaCommand"]
