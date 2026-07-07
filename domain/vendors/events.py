from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import uuid


@dataclass(frozen=True)
class VendorDomainEvent:
    occurred_at: datetime


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
class ServicePackageCreated(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class ServicePackageUpdated(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class ServicePackageSubmittedForApproval(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class ServicePackageApproved(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class ServicePackageRejected(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class ServicePackageActivated(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class ServicePackageDeactivated(VendorDomainEvent):
    package_id: uuid.UUID
    vendor_id: uuid.UUID


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


@dataclass(frozen=True)
class InquiryReceived(VendorDomainEvent):
    inquiry_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class InquiryRead(VendorDomainEvent):
    inquiry_id: uuid.UUID
    vendor_id: uuid.UUID
