import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from domain.shared.utils import utc_now
from domain.vendors.package_rules import coerce_package_price


class VendorStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class ServiceCategory(str, Enum):
    PHOTOGRAPHY = "photography"
    CATERING = "catering"
    DECOR = "decor"
    VENUE = "venue"
    ENTERTAINMENT = "entertainment"
    TRANSPORTATION = "transportation"
    ATTIRE = "attire"
    OTHER = "other"


@dataclass
class VendorProfile:
    id: uuid.UUID
    user_id: uuid.UUID
    business_name: str
    category: ServiceCategory
    description: str
    service_area: str  # e.g., "Kigali, Rwanda"
    contact_email: str
    contact_phone: str
    custom_category: Optional[str] = None
    website: Optional[str] = None
    profile_image_url: Optional[str] = None
    profile_image_public_id: Optional[str] = None
    cover_image_url: Optional[str] = None
    cover_image_public_id: Optional[str] = None
    status: VendorStatus = VendorStatus.DRAFT
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def required_profile_fields(cls) -> tuple[str, ...]:
        return (
            "business_name",
            "category",
            "description",
            "service_area",
            "contact_email",
            "contact_phone",
        )

    def get_profile_completion_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        for field_name in self.required_profile_fields():
            value = getattr(self, field_name, None)
            if value is None or not str(value).strip():
                errors[field_name] = ["This field is required."]
        if self.description and len(self.description.strip()) < 20:
            errors["description"] = ["Use at least 20 characters for your description."]
        if self.category == ServiceCategory.OTHER and not (self.custom_category or "").strip():
            errors["custom_category"] = ["Tell us what service you provide when choosing Other."]
        return errors

    @property
    def is_profile_complete(self) -> bool:
        return not self.get_profile_completion_errors()

    def submit_for_review(self) -> None:
        if self.status not in (VendorStatus.DRAFT, VendorStatus.REJECTED):
            raise ValueError(f"Cannot submit from status {self.status}")
        completion_errors = self.get_profile_completion_errors()
        if completion_errors:
            raise ValueError("Vendor profile setup is incomplete.")
        self.status = VendorStatus.PENDING_REVIEW
        self.submitted_at = utc_now()
        self.updated_at = utc_now()

    def approve(self) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise ValueError("Only pending profiles can be approved")
        self.status = VendorStatus.APPROVED
        self.approved_at = utc_now()
        self.updated_at = utc_now()

    def reject(self, reason: str) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise ValueError("Only pending profiles can be rejected")
        self.status = VendorStatus.REJECTED
        self.rejected_at = utc_now()
        self.rejection_reason = reason
        self.updated_at = utc_now()

    def suspend(self) -> None:
        if self.status != VendorStatus.APPROVED:
            raise ValueError("Only approved vendors can be suspended")
        self.status = VendorStatus.SUSPENDED
        self.updated_at = utc_now()

    def reinstate(self) -> None:
        if self.status != VendorStatus.SUSPENDED:
            raise ValueError("Only suspended vendors can be reinstated")
        self.status = VendorStatus.APPROVED
        self.updated_at = utc_now()


@dataclass
class PortfolioImage:
    id: uuid.UUID
    vendor_id: uuid.UUID
    public_id: str           # Cloudinary public_id
    secure_url: str          # Cloudinary URL
    caption: Optional[str] = None
    order: int = 0
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
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_caption(self, caption: Optional[str]) -> None:
        self.caption = caption

    def reorder(self, new_order: int) -> None:
        self.order = new_order

    def deactivate(self) -> None:
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.updated_at = utc_now()


@dataclass
class ServicePackage:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    # Money must remain Decimal after serializer/database validation. Converting to float can introduce
    # binary rounding drift and make package prices unsafe for approval, display, and future payment flows.
    price: Decimal
    currency: str = "RWF"      # Rwandan Franc
    package_tier: str = "standard"
    approval_status: str = "waiting_approval"
    rejection_reason: Optional[str] = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    last_approved_at: Optional[datetime] = None
    last_vendor_public_edit_at: Optional[datetime] = None
    next_vendor_edit_allowed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.price = coerce_package_price(self.price)

    def update_details(self, name: Optional[str] = None, description: Optional[str] = None,
                       price: Optional[Decimal] = None, currency: Optional[str] = None,
                       package_tier: Optional[str] = None) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if price is not None:
            self.price = coerce_package_price(price)
        if currency is not None:
            self.currency = currency
        if package_tier is not None:
            self.package_tier = package_tier
        self.updated_at = utc_now()

    def deactivate(self) -> None:
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.updated_at = utc_now()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = utc_now()


@dataclass
class Inquiry:
    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    client_phone: Optional[str] = None
    event_date: Optional[datetime] = None
    is_read: bool = False
    created_at: datetime = field(default_factory=utc_now)
