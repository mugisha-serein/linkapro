from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Optional, TypeVar
import uuid

T = TypeVar("T")


@dataclass(frozen=True)
class PageDTO(Generic[T]):
    items: tuple[T, ...]
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None


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
    profile_image_url: Optional[str]
    cover_image_url: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    rejection_reason: Optional[str]
    version: int


@dataclass(frozen=True)
class PortfolioImageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    secure_url: str
    caption: Optional[str]
    order: int
    media_type: str
    upload_status: str
    quality_status: str
    visibility_status: str
    is_active: bool
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
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    version: int = 0


@dataclass(frozen=True)
class ServicePackageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str
    package_tier: str
    approval_status: str
    rejection_reason: Optional[str]
    is_active: bool
    is_deleted: bool
    deleted_at: Optional[datetime]
    version: int


@dataclass(frozen=True)
class InquiryDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    client_phone: Optional[str]
    message: str
    event_date: Optional[date]
    is_read: bool
    created_at: datetime
    version: int
