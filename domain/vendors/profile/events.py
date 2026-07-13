from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.vendors.shared.aggregate import VendorDomainEvent

@dataclass(frozen=True)
class VendorSubmittedForReview(VendorDomainEvent):
    vendor_id: uuid.UUID
    user_id: uuid.UUID

@dataclass(frozen=True)
class VendorApproved(VendorDomainEvent):
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class VendorRejected(VendorDomainEvent):
    vendor_id: uuid.UUID
    reason: str

@dataclass(frozen=True)
class VendorSuspended(VendorDomainEvent):
    vendor_id: uuid.UUID
    reason: str | None = None

@dataclass(frozen=True)
class VendorReinstated(VendorDomainEvent):
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class VendorProfileUpdated(VendorDomainEvent):
    vendor_id: uuid.UUID
    user_id: uuid.UUID
