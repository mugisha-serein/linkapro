"""Command for deactivating an account."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class DeactivateUserCommand:
    user_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


__all__ = ["DeactivateUserCommand"]
