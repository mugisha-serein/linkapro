from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import uuid

@dataclass(frozen=True)
class VendorProfileDTO:
    id: uuid.UUID
    user_id: uuid.UUID
    business_name: str
    category: str
    description: str
    service_area: str
    contact_email: str
    contact_phone: str
    custom_category: Optional[str]
    website: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    rejection_reason: Optional[str]

@dataclass(frozen=True)
class PortfolioImageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    secure_url: str
    caption: Optional[str]
    order: int
    media_type: str = "image"
    upload_status: str = "uploaded"
    quality_status: str = "passed"
    visibility_status: str = "approved"
    upload_error: Optional[str] = None
    failure_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: str = ""
    file_size: int = 0
    local_preview_url: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    cloudinary_secure_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    analyzer_score: Optional[int] = None
    analyzer_summary: Optional[str] = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

@dataclass(frozen=True)
class ServicePackageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: float
    currency: str
    package_tier: str
    approval_status: str
    rejection_reason: Optional[str]
    is_active: bool
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

@dataclass(frozen=True)
class InquiryDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    client_phone: Optional[str]
    message: str
    event_date: Optional[datetime]
    is_read: bool
    created_at: datetime
