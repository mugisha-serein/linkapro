"""Command objects for payment write operations."""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from payments.domain.value_objects import Money, Currency
from payments.domain.enums import PaymentMethod, PaymentEnv


@dataclass(frozen=True)
class InitiatePaymentCommand:
    user_id: UUID
    amount: Money
    method: PaymentMethod
    idempotency_key: str
    redirect_base_url: str
    customer_email: str
    customer_name: Optional[str] = None
    context_reference: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    environment: PaymentEnv = PaymentEnv.TEST


@dataclass(frozen=True)
class ProcessWebhookCommand:
    event_id: str
    event_type: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    now: datetime
    encrypted_payload: Optional[str] = None 


@dataclass(frozen=True)
class ExpireStalePaymentsCommand:
    now: datetime  # Injected for testability


@dataclass(frozen=True)
class RequestRefundCommand:
    payment_reference: str
    requested_by: UUID
    reason: Optional[str] = None
    now: datetime = None  # Optional; if not provided, handler uses utc_now()