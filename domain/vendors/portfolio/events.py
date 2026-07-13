from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.vendors.shared.aggregate import VendorDomainEvent

@dataclass(frozen=True)
class PortfolioMediaQueued(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaProcessingStarted(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaUploaded(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaFailed(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID
    reason: str

@dataclass(frozen=True)
class PortfolioMediaSubmittedForApproval(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaApproved(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaRejected(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID
    reason: str

@dataclass(frozen=True)
class PortfolioMediaDeactivated(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class PortfolioMediaReordered(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID
    order: int

@dataclass(frozen=True)
class PortfolioCaptionUpdated(VendorDomainEvent):
    image_id: uuid.UUID
    vendor_id: uuid.UUID
