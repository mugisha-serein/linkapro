"""Password reset token domain model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid


class PasswordResetTokenStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class PasswordResetToken:
    id: uuid.UUID
    user_id: uuid.UUID
    jti: str
    token_hash: str
    status: PasswordResetTokenStatus
    expires_at: datetime
    used_at: datetime | None = None
    used_ip_hash: str | None = None
    used_user_agent_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.jti or not self.jti.strip():
            raise ValueError("Password reset token jti cannot be empty")
        if not self.token_hash or not self.token_hash.strip():
            raise ValueError("Password reset token hash cannot be empty")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("Password reset token expiry must be timezone-aware")
        if self.used_at and (self.used_at.tzinfo is None or self.used_at.utcoffset() is None):
            raise ValueError("Password reset token used time must be timezone-aware")

    def is_expired(self, *, now: datetime) -> bool:
        self._validate_now(now)
        return self.expires_at <= now

    def mark_used(
        self,
        *,
        now: datetime,
        used_ip_hash: str | None,
        used_user_agent_hash: str | None,
    ) -> "PasswordResetToken":
        self._validate_now(now)
        return PasswordResetToken(
            id=self.id,
            user_id=self.user_id,
            jti=self.jti,
            token_hash=self.token_hash,
            status=PasswordResetTokenStatus.USED,
            expires_at=self.expires_at,
            used_at=now,
            used_ip_hash=used_ip_hash,
            used_user_agent_hash=used_user_agent_hash,
        )

    def mark_expired(self) -> "PasswordResetToken":
        return PasswordResetToken(
            id=self.id,
            user_id=self.user_id,
            jti=self.jti,
            token_hash=self.token_hash,
            status=PasswordResetTokenStatus.EXPIRED,
            expires_at=self.expires_at,
            used_at=self.used_at,
            used_ip_hash=self.used_ip_hash,
            used_user_agent_hash=self.used_user_agent_hash,
        )

    def mark_revoked(self) -> "PasswordResetToken":
        return PasswordResetToken(
            id=self.id,
            user_id=self.user_id,
            jti=self.jti,
            token_hash=self.token_hash,
            status=PasswordResetTokenStatus.REVOKED,
            expires_at=self.expires_at,
            used_at=self.used_at,
            used_ip_hash=self.used_ip_hash,
            used_user_agent_hash=self.used_user_agent_hash,
        )

    @staticmethod
    def _validate_now(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
