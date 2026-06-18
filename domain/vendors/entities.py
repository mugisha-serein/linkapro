import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

from domain.shared.utils import utc_now


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
            errors["custom_category"] = ["Describe what you do when category is Other."]
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
    upload_status: str = "completed"
    upload_error: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)

    def update_caption(self, caption: Optional[str]) -> None:
        self.caption = caption

    def reorder(self, new_order: int) -> None:
        self.order = new_order


@dataclass
class ServicePackage:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: float               # in local currency
    currency: str = "RWF"      # Rwandan Franc
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_details(self, name: Optional[str] = None, description: Optional[str] = None,
                       price: Optional[float] = None) -> None:
        if name: self.name = name
        if description: self.description = description
        if price is not None: self.price = price
        self.updated_at = utc_now()

    def deactivate(self) -> None:
        self.is_active = False
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
