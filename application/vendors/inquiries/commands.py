from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
import uuid

from application.vendors.errors import InvalidVendorCommand
from application.vendors.shared.commands import (
    AuthenticatedActor,
    _coerce_actor,
    _coerce_expected_version,
    _coerce_required_idempotency_key,
    _coerce_uuid,
)

@dataclass(frozen=True)
class SendInquiryCommand:
    vendor_id: uuid.UUID
    requester_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    idempotency_key: str
    client_phone: Optional[str] = None
    event_date: Optional[date] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "requester_id", _coerce_uuid(self.requester_id, "requester_id"))
        if self.event_date is not None and (isinstance(self.event_date, datetime) or type(self.event_date) is not date):
            raise InvalidVendorCommand(field_errors={"event_date": ["Must be a date or null."]})
        object.__setattr__(self, "idempotency_key", _coerce_required_idempotency_key(self.idempotency_key))

@dataclass(frozen=True)
class MarkInquiryReadCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    inquiry_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "inquiry_id", _coerce_uuid(self.inquiry_id, "inquiry_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
