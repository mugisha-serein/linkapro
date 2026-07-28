"""Verification-domain events."""
from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Optional

from domain.identity.shared import DomainEvent, SecurityReason

from .verification_purpose import VerificationPurpose


def _normalize_reason(reason: Optional[SecurityReason | str]) -> Optional[SecurityReason]:
    if reason is None or isinstance(reason, SecurityReason):
        return reason
    return SecurityReason(reason)


@dataclass(frozen=True)
class UserVerified(DomainEvent):
    user_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    reason: Optional[SecurityReason | str] = None
    auth_token_version: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _normalize_reason(self.reason))


@dataclass(frozen=True)
class VerificationChallengeIssued(DomainEvent):
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    purpose: VerificationPurpose | str
    expires_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", VerificationPurpose(self.purpose))


@dataclass(frozen=True)
class VerificationChallengeSucceeded(DomainEvent):
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    purpose: VerificationPurpose | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", VerificationPurpose(self.purpose))


@dataclass(frozen=True)
class VerificationChallengeExpired(DomainEvent):
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    purpose: VerificationPurpose | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", VerificationPurpose(self.purpose))


@dataclass(frozen=True)
class VerificationChallengeResent(DomainEvent):
    user_id: uuid.UUID
    challenge_id: uuid.UUID
    purpose: VerificationPurpose | str
    resend_available_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", VerificationPurpose(self.purpose))
