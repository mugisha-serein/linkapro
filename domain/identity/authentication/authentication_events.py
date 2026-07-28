"""Authentication-domain events."""
from dataclasses import dataclass
import uuid
from typing import Optional

from domain.identity.shared import DomainEvent


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    user_id: uuid.UUID
    auth_token_version: Optional[int] = None
