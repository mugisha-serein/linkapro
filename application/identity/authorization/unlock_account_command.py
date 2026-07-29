"""Command for unlocking an account."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class UnlockAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: Optional[str] = None


__all__ = ["UnlockAccountCommand"]
