"""Domain events for identity context."""
from dataclasses import dataclass, field
import uuid
from datetime import datetime
from typing import Optional

from .value_objects import Email
from .entities import UserRole


@dataclass(frozen=True)
class UserRegistered:
    user_id: uuid.UUID
    email: Email
    role: UserRole
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UserLoggedIn:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(frozen=True)
class UserPasswordChanged:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UserTwoFactorEnabled:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UserTwoFactorDisabled:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UserOAuthLinked:
    user_id: uuid.UUID
    provider: str
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class UserDeactivated:
    user_id: uuid.UUID
    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None
