from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import uuid

@dataclass(frozen=True)
class CreateVendorProfileCommand:
    user_id: uuid.UUID
    business_name: str
    category: str
    description: str
    service_area: str
    contact_email: str
    contact_phone: str
    custom_category: Optional[str] = None
    website: Optional[str] = None

@dataclass(frozen=True)
class UpdateVendorProfileCommand:
    vendor_id: uuid.UUID
    business_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    service_area: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    custom_category: Optional[str] = None
    website: Optional[str] = None

@dataclass(frozen=True)
class SubmitVendorForReviewCommand:
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class ApproveVendorCommand:
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class RejectVendorCommand:
    vendor_id: uuid.UUID
    reason: str

@dataclass(frozen=True)
class SuspendVendorCommand:
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class ReinstateVendorCommand:
    vendor_id: uuid.UUID

@dataclass(frozen=True)
class AddPortfolioImageCommand:
    vendor_id: uuid.UUID
    public_id: str
    secure_url: str
    caption: Optional[str] = None

@dataclass(frozen=True)
class DeletePortfolioImageCommand:
    image_id: uuid.UUID

@dataclass(frozen=True)
class ReorderPortfolioImagesCommand:
    vendor_id: uuid.UUID
    image_ids_in_order: List[uuid.UUID]

@dataclass(frozen=True)
class CreateServicePackageCommand:
    vendor_id: uuid.UUID
    name: str
    description: str
    price: float
    currency: str = "RWF"
    package_tier: str = "standard"

@dataclass(frozen=True)
class UpdateServicePackageCommand:
    package_id: uuid.UUID
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    package_tier: Optional[str] = None

@dataclass(frozen=True)
class DeactivateServicePackageCommand:
    package_id: uuid.UUID
    deleted_by_id: Optional[uuid.UUID] = None

@dataclass(frozen=True)
class ActivateServicePackageCommand:
    package_id: uuid.UUID

@dataclass(frozen=True)
class SendInquiryCommand:
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    client_phone: Optional[str] = None
    event_date: Optional[datetime] = None
