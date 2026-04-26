import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .value_objects import Money
from .enums import PaymentStatus, PaymentMethod, PaymentEnv
from domain.shared.utils import utc_now


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


@dataclass
class Payment:
    id: uuid.UUID
    user_id: uuid.UUID
    amount: Money
    method: PaymentMethod
    reference: str                    # internal UUID-based string
    idempotency_key: str              # UUID string
    environment: PaymentEnv
    status: PaymentStatus = PaymentStatus.INITIATED
    provider_reference: Optional[str] = None
    context_reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    expires_at: Optional[datetime] = None

    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=30)
        # Validate metadata
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        if len(self.metadata) > 10:
            raise ValueError("metadata cannot exceed 10 keys")
        for k, v in self.metadata.items():
            if not isinstance(k, str) or not isinstance(v, (str, int, float, bool)):
                raise ValueError("metadata keys must be strings, values must be primitive")

    def transition_to(self, new_status: PaymentStatus, now: datetime) -> None:
        """State machine for valid transitions."""
        allowed = self._allowed_transitions().get(self.status, [])
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.status.value} to {new_status.value}"
            )
        self.status = new_status

    def _allowed_transitions(self):
        from .enums import PaymentStatus as S
        return {
            S.INITIATED: [S.PENDING, S.CANCELLED, S.EXPIRED],
            S.PENDING: [S.SUCCESS, S.FAILED, S.CANCELLED, S.EXPIRED],
            S.SUCCESS: [S.REFUND_REQUESTED],
            S.REFUND_REQUESTED: [S.REFUNDED, S.SUCCESS],
            S.FAILED: [],
            S.CANCELLED: [],
            S.EXPIRED: [],
            S.REFUNDED: [],
        }

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at < now


@dataclass
class AuditEvent:
    id: uuid.UUID
    payment_id: uuid.UUID
    action: str
    actor: str                     # "system", "user:{uuid}", "webhook"
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)