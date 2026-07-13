from __future__ import annotations

import uuid
from dataclasses import dataclass

from domain.vendors.shared.aggregate import VendorDomainEvent

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
