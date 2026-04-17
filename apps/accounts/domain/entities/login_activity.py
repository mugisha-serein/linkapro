# domain/entities/login_activity.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.value_objects import (
    LoginOutcome,
    UserId,
    SessionId,
    utc_now,
)


# ══════════════════════════════════════════════════════════
# LOGIN ACTIVITY — AUDIT ENTITY
#
# Immutable log of every authentication event.
# Append-only by convention: no setters, no mutation methods.
# The domain layer creates these records; infrastructure persists them.
# ══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LoginActivity:
    """
    Immutable record of a single authentication event.

    Rules:
    - Frozen dataclass — no field may be modified after creation.
    - Every login attempt (success, failure, or blocked) produces one record.
    - Provides full context: who, from where, on what device, with what outcome.
    - session_id is None for blocked/failed attempts that never produced a session.

    Auditability guarantee:
    - outcome is always one of: SUCCESS / FAILURE / BLOCKED
    - failure_reason is required whenever outcome != SUCCESS
    - Records carry their own timestamp; infrastructure must not alter it.
    """

    id: str
    user_id: Optional[UserId]         # None only for unknown-user attempts
    outcome: LoginOutcome
    occurred_at: datetime
    ip_address: str
    user_agent: str
    device_fingerprint_raw: Optional[str] = None
    session_id: Optional[SessionId] = None
    failure_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    # ── Factories (the only way to create a record) ───────

    @classmethod
    def record_success(
        cls,
        user_id: UserId,
        session_id: SessionId,
        ip_address: str,
        user_agent: str,
        device_fingerprint_raw: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "LoginActivity":
        """Log a successful authentication."""
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            outcome=LoginOutcome.SUCCESS,
            occurred_at=utc_now(),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint_raw=device_fingerprint_raw,
            session_id=session_id,
            failure_reason=None,
            metadata=metadata or {},
        )

    @classmethod
    def record_failure(
        cls,
        user_id: Optional[UserId],
        ip_address: str,
        user_agent: str,
        failure_reason: str,
        device_fingerprint_raw: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "LoginActivity":
        """
        Log a failed authentication attempt.
        user_id may be None when the submitted email doesn't match any user
        (avoids leaking user existence, but still auditable).
        """
        if not failure_reason:
            raise ValueError("failure_reason is required for FAILURE records.")
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            outcome=LoginOutcome.FAILURE,
            occurred_at=utc_now(),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint_raw=device_fingerprint_raw,
            session_id=None,
            failure_reason=failure_reason,
            metadata=metadata or {},
        )

    @classmethod
    def record_blocked(
        cls,
        user_id: UserId,
        ip_address: str,
        user_agent: str,
        failure_reason: str,
        device_fingerprint_raw: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> "LoginActivity":
        """
        Log an attempt that was blocked before credentials were checked
        (e.g. account locked, account inactive, rate-limited).
        """
        if not failure_reason:
            raise ValueError("failure_reason is required for BLOCKED records.")
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            outcome=LoginOutcome.BLOCKED,
            occurred_at=utc_now(),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint_raw=device_fingerprint_raw,
            session_id=None,
            failure_reason=failure_reason,
            metadata=metadata or {},
        )

    # ── Query helpers (read-only) ─────────────────────────

    @property
    def was_successful(self) -> bool:
        return self.outcome == LoginOutcome.SUCCESS

    @property
    def was_blocked(self) -> bool:
        return self.outcome == LoginOutcome.BLOCKED

    @property
    def was_failed(self) -> bool:
        return self.outcome == LoginOutcome.FAILURE

    def __repr__(self) -> str:
        uid = str(self.user_id) if self.user_id else "unknown"
        return (
            f"<LoginActivity id={self.id[:8]}… "
            f"user={uid[:8]}… "
            f"outcome={self.outcome.value} "
            f"at={self.occurred_at.isoformat()}>"
        )