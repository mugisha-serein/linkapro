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
    upload_status: str = "completed"
    upload_error: Optional[str] = None
    original_filename: Optional[str] = None

@dataclass(frozen=True)
class ServicePackageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: float
    currency: str
    is_active: bool

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
