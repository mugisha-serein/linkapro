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

    def __post_init__(self) -> None:
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise ValueError("Page total must be a nonnegative integer.")
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise ValueError("Page limit must be an integer.")
        if not isinstance(self.offset, int) or isinstance(self.offset, bool):
            raise ValueError("Page offset must be an integer.")
        if self.limit < 1 or self.limit > 100:
            raise ValueError("Page limit must be between 1 and 100.")
        if self.offset < 0 or self.offset > 10_000:
            raise ValueError("Page offset must be between 0 and 10000.")
        if len(self.items) > self.limit:
            raise ValueError("Page items cannot exceed the page limit.")
        if self.total < len(self.items):
            raise ValueError("Page total cannot be less than the number of items.")
        if self.next_cursor is not None:
            if not isinstance(self.next_cursor, str):
                raise ValueError("Page next_cursor must be a string.")
            next_cursor = self.next_cursor.strip()
            if not next_cursor:
                raise ValueError("Page next_cursor cannot be blank.")
            if len(next_cursor) > 512:
                raise ValueError("Page next_cursor must be 512 characters or fewer.")
            object.__setattr__(self, "next_cursor", next_cursor)


@dataclass(frozen=True)
class VendorDashboardSummaryDTO:
    profile_completion: int
    total_inquiries: int
    inquiries_mtd: int
    unread_inquiries: int
    read_inquiries: int
    response_rate: int
    total_packages: int
    active_packages: int
    approved_packages: int
    pending_packages: int
    rejected_packages: int
    portfolio_count: int
    account_status: str
    service_area: str


@dataclass(frozen=True)
class VendorAnalyticsDTO:
    profile_completion: int
    total_inquiries: int
    inquiries_mtd: int
    unread_inquiries: int
    read_inquiries: int
    response_rate: float
    total_packages: int
    active_packages: int
    approved_packages: int
    pending_packages: int
    rejected_packages: int
    portfolio_count: int
    account_status: str
    service_area: str
    avg_response_time_hours: float | None
    conversion_rate: float | None
    unavailable_metrics: tuple[str, ...]


@dataclass(frozen=True)
class VendorActivityDTO:
    id: str
    type: str
    message: str
    created_at: str


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
    version: int
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
    last_approved_at: Optional[datetime]
    last_vendor_public_edit_at: Optional[datetime]
    next_vendor_edit_allowed_at: Optional[datetime]
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
