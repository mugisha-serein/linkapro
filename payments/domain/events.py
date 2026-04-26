from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class FraudSignalEvent:
    payment_id: UUID
    provider_reference: str
    reason: str
    occurred_at: datetime


@dataclass(frozen=True)
class PaymentCompleted:
    payment_id: UUID
    user_id: UUID
    amount_minor: int
    currency: str
    occurred_at: datetime


@dataclass(frozen=True)
class PaymentExpired:
    payment_id: UUID
    occurred_at: datetime