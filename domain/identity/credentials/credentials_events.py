"""Credential-domain events."""
from dataclasses import dataclass
import uuid
from typing import Optional

from domain.identity.shared import DomainEvent, SecurityReason


def _normalize_reason(reason: Optional[SecurityReason | str]) -> Optional[SecurityReason]:
    if reason is None or isinstance(reason, SecurityReason):
        return reason
    return SecurityReason(reason)


@dataclass(frozen=True)
class UserPasswordChanged(DomainEvent):
    user_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))
