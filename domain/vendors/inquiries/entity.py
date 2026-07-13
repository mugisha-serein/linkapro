from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import ClassVar, Optional

from domain.shared.utils import utc_now
from domain.vendors.inquiries.errors import InquiryValidationError
from domain.vendors.inquiries.events import InquiryRead, InquiryReceived
from domain.vendors.shared.aggregate import (
    DomainAggregate,
    _normalize_bool,
    _normalize_datetime,
    _normalize_email,
    _normalize_event_date,
    _normalize_optional_phone,
    _normalize_text,
    _normalize_uuid,
    _normalize_version,
)
from domain.vendors.shared.validation import (
    MIN_INQUIRY_MESSAGE_LENGTH,
    TEXT_LIMITS,
    normalize_event_date,
    validate_new_event_date_bounds,
)

@dataclass
class Inquiry(DomainAggregate):
    _protected_fields: ClassVar[frozenset[str]] = frozenset({"is_read", "version"})

    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    client_phone: Optional[str] = None
    event_date: Optional[date] = None
    is_read: bool = False
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
        self.validate_invariants()
        self._lock_state()

    @classmethod
    def create(
        cls,
        *,
        vendor_id: uuid.UUID,
        client_name: str,
        client_email: str,
        message: str,
        client_phone: Optional[str] = None,
        event_date: Optional[date] = None,
    ) -> "Inquiry":
        try:
            checked_event_date = validate_new_event_date_bounds(normalize_event_date(event_date))
        except ValueError as exc:
            raise InquiryValidationError(field_errors={"event_date": [str(exc)]}) from exc
        inquiry = cls(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            client_name=client_name,
            client_email=client_email,
            message=message,
            client_phone=client_phone,
            event_date=checked_event_date,
        )
        inquiry._record(
            InquiryReceived(
                inquiry_id=inquiry.id,
                vendor_id=inquiry.vendor_id,
                occurred_at=inquiry.created_at,
                aggregate_id=inquiry.id,
                aggregate_version=inquiry.version,
            )
        )
        return inquiry

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.vendor_id = _normalize_uuid(self.vendor_id, "vendor_id", errors)
        self.client_name = _normalize_text(
            self.client_name,
            "client_name",
            TEXT_LIMITS["client_name"],
            errors,
        )
        self.client_email = _normalize_email(self.client_email, "client_email", errors)
        self.client_phone = _normalize_optional_phone(self.client_phone, "client_phone", errors)
        self.message = _normalize_text(
            self.message,
            "message",
            TEXT_LIMITS["message"],
            errors,
            min_length=MIN_INQUIRY_MESSAGE_LENGTH,
        )
        self.event_date = _normalize_event_date(self.event_date, "event_date", errors)
        self.is_read = _normalize_bool(self.is_read, "is_read", errors)
        self.version = _normalize_version(self.version, errors)
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        if errors:
            raise InquiryValidationError(field_errors=errors)

    def mark_read(self) -> None:
        if self.is_read:
            return
        now = utc_now()
        candidate = replace(self, is_read=True)
        self._commit_candidate(
            candidate,
            lambda version: InquiryRead(
                inquiry_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )
