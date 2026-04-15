# Domain Entity - Pure Business Logic
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Session:
    """
    Session domain entity.

    Represents a user session in the business domain with session lifecycle rules.
    """

    class State:
        ACTIVE = "ACTIVE"
        REVOKED = "REVOKED"
        EXPIRED = "EXPIRED"
        SUSPICIOUS = "SUSPICIOUS"
        LOCKED = "LOCKED"

    user_id: UUID
    session_key: str
    ip_address: str
    user_agent: str
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    state: str = State.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    risk_score: int = 0

    def __post_init__(self):
        """Validate business invariants."""
        self._validate_state()
        self._validate_dates()

    def _validate_state(self) -> None:
        """Ensure state is valid."""
        valid_states = [self.State.ACTIVE, self.State.REVOKED,
                       self.State.EXPIRED, self.State.SUSPICIOUS, self.State.LOCKED]
        if self.state not in valid_states:
            raise ValueError(f"Invalid session state: {self.state}")

    def _validate_dates(self) -> None:
        """Ensure date relationships are valid."""
        if self.expires_at <= self.created_at:
            raise ValueError("Expiration date must be after creation date")

        if self.revoked_at and self.revoked_at < self.created_at:
            raise ValueError("Revocation date cannot be before creation date")

    def is_active(self) -> bool:
        """Business rule: Determine if session is currently active."""
        if self.state != self.State.ACTIVE:
            return False

        if datetime.now() > self.expires_at:
            return False

        return True

    def is_expired(self) -> bool:
        """Business rule: Check if session has expired."""
        return datetime.now() > self.expires_at

    def can_be_used_for_authentication(self) -> bool:
        """Business rule: Determine if session can be used for authentication."""
        return self.is_active() and self.risk_score < 80

    def revoke(self, reason: str) -> Session:
        """Business logic: Revoke the session."""
        return Session(
            id=self.id,
            user_id=self.user_id,
            session_key=self.session_key,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            state=self.State.REVOKED,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            expires_at=self.expires_at,
            revoked_at=datetime.now(),
            revoked_reason=reason,
            risk_score=self.risk_score,
        )

    def update_last_used(self) -> Session:
        """Business logic: Update last used timestamp."""
        return Session(
            id=self.id,
            user_id=self.user_id,
            session_key=self.session_key,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            state=self.state,
            created_at=self.created_at,
            last_used_at=datetime.now(),
            expires_at=self.expires_at,
            revoked_at=self.revoked_at,
            revoked_reason=self.revoked_reason,
            risk_score=self.risk_score,
        )

    def mark_suspicious(self, risk_score: int) -> Session:
        """Business logic: Mark session as suspicious."""
        new_state = self.State.SUSPICIOUS if risk_score >= 60 else self.state

        return Session(
            id=self.id,
            user_id=self.user_id,
            session_key=self.session_key,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            state=new_state,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            expires_at=self.expires_at,
            revoked_at=self.revoked_at,
            revoked_reason=self.revoked_reason,
            risk_score=risk_score,
        )