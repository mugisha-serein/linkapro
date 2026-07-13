from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.vendors.shared.aggregate import VendorDomainEvent

@dataclass(frozen=True)
class InquiryReceived(VendorDomainEvent):
    inquiry_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class InquiryRead(VendorDomainEvent):
    inquiry_id: uuid.UUID
    vendor_id: uuid.UUID
