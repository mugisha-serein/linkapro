"""Command for reactivating an account."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class ReactivateAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: Optional[str] = None


__all__ = ["ReactivateAccountCommand"]
