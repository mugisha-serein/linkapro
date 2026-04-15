# Domain Events - Business Event Notifications
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent(ABC):
    """Base class for domain events."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.now)
    event_version: int = 1

    @property
    def event_type(self) -> str:
        """Return the event type name."""
        return self.__class__.__name__


@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    """Event: User account was registered."""

    user_id: UUID
    email: str
    role: str

    def __post_init__(self):
        # Could add validation or business rules here
        pass


@dataclass(frozen=True)
class UserLoggedInEvent(DomainEvent):
    """Event: User successfully logged in."""

    user_id: UUID
    session_id: UUID
    ip_address: str
    user_agent: str


@dataclass(frozen=True)
class UserLoginFailedEvent(DomainEvent):
    """Event: User login attempt failed."""

    user_id: UUID
    email: str
    ip_address: str
    user_agent: str
    failure_reason: str


@dataclass(frozen=True)
class UserPasswordChangedEvent(DomainEvent):
    """Event: User changed password."""

    user_id: UUID
    changed_at: datetime


@dataclass(frozen=True)
class UserAccountLockedEvent(DomainEvent):
    """Event: User account was locked."""

    user_id: UUID
    locked_until: datetime
    reason: str


@dataclass(frozen=True)
class UserAccountUnlockedEvent(DomainEvent):
    """Event: User account was unlocked."""

    user_id: UUID
    unlocked_at: datetime


@dataclass(frozen=True)
class SessionCreatedEvent(DomainEvent):
    """Event: User session was created."""

    session_id: UUID
    user_id: UUID
    ip_address: str
    user_agent: str


@dataclass(frozen=True)
class SessionRevokedEvent(DomainEvent):
    """Event: User session was revoked."""

    session_id: UUID
    user_id: UUID
    revoked_reason: str


@dataclass(frozen=True)
class SuspiciousActivityDetectedEvent(DomainEvent):
    """Event: Suspicious activity was detected."""

    user_id: UUID
    activity_type: str
    risk_score: int
    details: dict[str, Any]


# Event collection and handling could be added here
class DomainEventPublisher:
    """Simple domain event publisher (could be enhanced with actual pub/sub)."""

    _handlers: dict[str, list[callable]] = {}

    @classmethod
    def subscribe(cls, event_type: str, handler: callable):
        """Subscribe to domain events."""
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        cls._handlers[event_type].append(handler)

    @classmethod
    def publish(cls, event: DomainEvent):
        """Publish a domain event."""
        event_type = event.event_type
        if event_type in cls._handlers:
            for handler in cls._handlers[event_type]:
                try:
                    handler(event)
                except Exception:
                    # In domain layer, we define that handlers should not fail
                    # the business operation, but this would be logged
                    pass