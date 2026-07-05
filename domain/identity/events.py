"""Domain events for identity context."""
from dataclasses import dataclass, field
import uuid
from datetime import datetime
from typing import Optional

from .value_objects import Email, SecurityReason
from .entities import UserRole


def _normalize_reason(reason: Optional[SecurityReason | str]) -> Optional[SecurityReason]:
    if reason is None or isinstance(reason, SecurityReason):
        return reason
    return SecurityReason(reason)


@dataclass(frozen=True)
class UserRegistered:
    user_id: uuid.UUID
    email: Email
    role: UserRole
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class UserLoggedIn:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    auth_token_version: Optional[int] = None


@dataclass(frozen=True)
class UserPasswordChanged:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class UserTwoFactorEnabled:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class UserTwoFactorDisabled:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class UserOAuthLinked:
    user_id: uuid.UUID
    provider: str
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class UserDeactivated:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))
