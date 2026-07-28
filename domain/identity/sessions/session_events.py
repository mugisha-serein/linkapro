"""Session-domain events."""
from dataclasses import dataclass
import uuid

from domain.identity.shared import DomainEvent


@dataclass(frozen=True)
class RefreshTokenRotated(DomainEvent):
    user_id: uuid.UUID | str
    token_family: str
    session_id: str | None = None


@dataclass(frozen=True)
class TokenFamilyRevoked(DomainEvent):
    token_family: str
    reason: str
    user_id: uuid.UUID | str | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class RefreshTokenReplayDetected(DomainEvent):
    token_family: str
    user_id: uuid.UUID | str | None = None
    session_id: str | None = None


__all__ = [
    "RefreshTokenReplayDetected",
    "RefreshTokenRotated",
    "TokenFamilyRevoked",
]
