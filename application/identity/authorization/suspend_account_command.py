"""Command for suspending an account."""

from dataclasses import dataclass
import uuid

from domain.identity.shared.security_reason import SecurityReason


@dataclass(frozen=True)
class SuspendAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: SecurityReason


__all__ = ["SuspendAccountCommand"]
