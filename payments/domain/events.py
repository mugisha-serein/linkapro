from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class FraudSignalEvent:
    payment_id: UUID
    provider_reference: str
    reason: str
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class PaymentCompleted:
    payment_id: UUID
    user_id: UUID
    amount_minor: int
    currency: str
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class PaymentExpired:
    payment_id: UUID
    occurred_at: datetime
    event_id: UUID = field(default_factory=uuid4)
