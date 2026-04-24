from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class PaymentInitiationDTO:
    reference: str
    payment_link: str
    expires_at: datetime


@dataclass(frozen=True)
class PaymentStatusDTO:
    reference: str
    status: str
    amount: str          # Formatted with currency
    minor_units: int
    currency: str
    method: str
    created_at: datetime
    expires_at: Optional[datetime]
    provider_reference: Optional[str]