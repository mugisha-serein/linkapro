"""Identity session model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from .session_id import SessionId
from .session_status import SessionStatus
from .token_family import TokenFamily


@dataclass(frozen=True)
class IdentitySession:
    id: SessionId
    user_id: uuid.UUID | str
    token_family: TokenFamily
    status: SessionStatus = SessionStatus.ACTIVE
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status is SessionStatus.ACTIVE

    def revoke(self, *, reason: str, now: datetime) -> "IdentitySession":
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
        return IdentitySession(
            id=self.id,
            user_id=self.user_id,
            token_family=self.token_family.revoke(),
            status=SessionStatus.REVOKED,
            revoked_at=now,
            revoked_reason=reason,
        )
