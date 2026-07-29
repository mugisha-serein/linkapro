"""Command for assigning account roles."""

from dataclasses import dataclass
from typing import Optional
import uuid

from domain.identity.account import AccountRole
from domain.identity.shared.security_reason import SecurityReason


@dataclass(frozen=True)
class AssignRoleCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    new_role: AccountRole
    reason: Optional[SecurityReason] = None


__all__ = ["AssignRoleCommand"]
