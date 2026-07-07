from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from domain.shared.utils import utc_now
from domain.vendors.errors import (
    InquiryValidationError,
    InvalidPackageTransition,
    InvalidPortfolioTransition,
    InvalidVendorTransition,
    PackageValidationError,
    PortfolioValidationError,
    VendorProfileValidationError,
)
from domain.vendors.package_rules import coerce_package_price
from domain.vendors.validation import (
    MAX_PORTFOLIO_ORDER,
    MIN_INQUIRY_MESSAGE_LENGTH,
    MIN_PACKAGE_DESCRIPTION_LENGTH,
    TEXT_LIMITS,
    add_error,
    aware_utc_datetime,
    bounded_text,
    normalize_currency,
    normalize_phone,
    positive_decimal,
    validate_email,
    validate_public_media_url,
    validate_safe_url,
    validate_uuid,
)


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


class PackageTier(str, Enum):
    STANDARD = "standard"
    PREMIER = "premier"
    GOLD = "gold"


class PackageApprovalStatus(str, Enum):
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class CurrencyCode(str, Enum):
    RWF = "RWF"
    USD = "USD"
    EUR = "EUR"
    KES = "KES"
    GHS = "GHS"
    NGN = "NGN"


class PortfolioMediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class PortfolioUploadStatus(str, Enum):
    STAGED = "staged"
    QUEUED = "queued"
    PROCESSING = "processing"
    UPLOADED = "uploaded"
    PROCESSING_DEFERRED = "processing_deferred"
    FAILED = "failed"


class PortfolioQualityStatus(str, Enum):
    PENDING_ANALYSIS = "pending_analysis"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class PortfolioVisibilityStatus(str, Enum):
    PRIVATE = "private"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class VendorProfile:
    id: uuid.UUID
    user_id: uuid.UUID
    business_name: str
    category: ServiceCategory
    description: str
    service_area: str
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

    def __post_init__(self) -> None:
        self.validate_invariants()

    @classmethod
    def create_draft(
        cls,
        *,
        user_id: uuid.UUID,
        business_name: str,
        category: ServiceCategory | str,
        description: str,
        service_area: str,
        contact_email: str,
        contact_phone: str,
        custom_category: Optional[str] = None,
        website: Optional[str] = None,
    ) -> "VendorProfile":
        return cls(
            id=uuid.uuid4(),
            user_id=user_id,
            business_name=business_name,
            category=category,
            description=description,
            service_area=service_area,
            contact_email=contact_email,
            contact_phone=contact_phone,
            custom_category=custom_category,
            website=website,
        )

    @classmethod
    def rehydrate(cls, **kwargs) -> "VendorProfile":
        return cls(**kwargs)

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

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.user_id = _normalize_uuid(self.user_id, "user_id", errors)
        self.business_name = _normalize_text(
            self.business_name,
            "business_name",
            TEXT_LIMITS["business_name"],
            errors,
        )
        self.description = _normalize_text(
            self.description,
            "description",
            TEXT_LIMITS["description"],
            errors,
        )
        self.service_area = _normalize_text(
            self.service_area,
            "service_area",
            TEXT_LIMITS["service_area"],
            errors,
        )
        self.contact_email = _normalize_email(self.contact_email, "contact_email", errors)
        self.contact_phone = _normalize_phone(self.contact_phone, "contact_phone", errors)
        self.custom_category = _normalize_optional_text(
            self.custom_category,
            "custom_category",
            TEXT_LIMITS["custom_category"],
            errors,
        )
        self.website = _normalize_safe_url(self.website, "website", errors)
        self.profile_image_url = _normalize_public_media_url(
            self.profile_image_url,
            "profile_image_url",
            errors,
        )
        self.cover_image_url = _normalize_public_media_url(
            self.cover_image_url,
            "cover_image_url",
            errors,
        )
        self.profile_image_public_id = _normalize_optional_text(
            self.profile_image_public_id,
            "profile_image_public_id",
            TEXT_LIMITS["public_id"],
            errors,
        )
        self.cover_image_public_id = _normalize_optional_text(
            self.cover_image_public_id,
            "cover_image_public_id",
            TEXT_LIMITS["public_id"],
            errors,
        )
        self.category = _normalize_enum(ServiceCategory, self.category, "category", errors)
        self.status = _normalize_enum(VendorStatus, self.status, "status", errors)
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        self.updated_at = _normalize_datetime(self.updated_at, "updated_at", errors, required=True)
        self.submitted_at = _normalize_datetime(self.submitted_at, "submitted_at", errors)
        self.approved_at = _normalize_datetime(self.approved_at, "approved_at", errors)
        self.rejected_at = _normalize_datetime(self.rejected_at, "rejected_at", errors)
        self.rejection_reason = _normalize_optional_text(
            self.rejection_reason,
            "rejection_reason",
            TEXT_LIMITS["rejection_reason"],
            errors,
        )

        if self.category == ServiceCategory.OTHER and not self.custom_category:
            add_error(errors, "custom_category", "Tell us what service you provide when choosing Other.")
        if self.category != ServiceCategory.OTHER and self.custom_category:
            pass
        _validate_public_id_url_pair(
            errors,
            url=self.profile_image_url,
            public_id=self.profile_image_public_id,
            url_field="profile_image_url",
            public_id_field="profile_image_public_id",
        )
        _validate_public_id_url_pair(
            errors,
            url=self.cover_image_url,
            public_id=self.cover_image_public_id,
            url_field="cover_image_url",
            public_id_field="cover_image_public_id",
        )
        if self.status == VendorStatus.PENDING_REVIEW and self.submitted_at is None:
            self.submitted_at = self.updated_at
        if self.status == VendorStatus.APPROVED and self.approved_at is None:
            self.approved_at = self.updated_at
        if self.status == VendorStatus.REJECTED:
            if not self.rejection_reason:
                add_error(errors, "rejection_reason", "Rejection reason is required.")
            if self.rejected_at is None:
                self.rejected_at = self.updated_at
        if self.status != VendorStatus.REJECTED and self.rejection_reason:
            add_error(errors, "rejection_reason", "Only rejected vendors can have rejection metadata.")

        if errors:
            raise VendorProfileValidationError(field_errors=errors)

    def get_profile_completion_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        for field_name in self.required_profile_fields():
            value = getattr(self, field_name, None)
            if value is None or not str(value).strip():
                errors[field_name] = ["This field is required."]
        if self.category == ServiceCategory.OTHER and not (self.custom_category or "").strip():
            errors["custom_category"] = ["Tell us what service you provide when choosing Other."]
        return errors

    @property
    def is_profile_complete(self) -> bool:
        return not self.get_profile_completion_errors()

    def submit_for_review(self) -> None:
        if self.status not in (VendorStatus.DRAFT, VendorStatus.REJECTED):
            raise InvalidVendorTransition(f"Cannot submit from status {self.status.value}")
        completion_errors = self.get_profile_completion_errors()
        if completion_errors:
            raise VendorProfileValidationError(
                "Vendor profile setup is incomplete.",
                field_errors=completion_errors,
            )
        now = utc_now()
        self.status = VendorStatus.PENDING_REVIEW
        self.submitted_at = now
        self.rejected_at = None
        self.rejection_reason = None
        self.updated_at = now
        self.validate_invariants()

    def approve(self) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise InvalidVendorTransition("Only pending profiles can be approved")
        now = utc_now()
        self.status = VendorStatus.APPROVED
        self.approved_at = now
        self.rejected_at = None
        self.rejection_reason = None
        self.updated_at = now
        self.validate_invariants()

    def reject(self, reason: str) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise InvalidVendorTransition("Only pending profiles can be rejected")
        clean_reason = _validated_transition_reason(reason, "rejection_reason", VendorProfileValidationError)
        now = utc_now()
        self.status = VendorStatus.REJECTED
        self.rejected_at = now
        self.rejection_reason = clean_reason
        self.updated_at = now
        self.validate_invariants()

    def suspend(self, reason: str | None = None) -> None:
        if self.status != VendorStatus.APPROVED:
            raise InvalidVendorTransition("Only approved vendors can be suspended")
        if reason is not None:
            _validated_transition_reason(reason, "reason", VendorProfileValidationError)
        now = utc_now()
        self.status = VendorStatus.SUSPENDED
        self.updated_at = now
        self.validate_invariants()

    def reinstate(self) -> None:
        if self.status != VendorStatus.SUSPENDED:
            raise InvalidVendorTransition("Only suspended vendors can be reinstated")
        now = utc_now()
        self.status = VendorStatus.APPROVED
        if self.approved_at is None:
            self.approved_at = now
        self.updated_at = now
        self.validate_invariants()


@dataclass
class PortfolioImage:
    id: uuid.UUID
    vendor_id: uuid.UUID
    public_id: str
    secure_url: str
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

    def __post_init__(self) -> None:
        self.validate_invariants()

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.vendor_id = _normalize_uuid(self.vendor_id, "vendor_id", errors)
        self.public_id = _normalize_optional_text(self.public_id, "public_id", TEXT_LIMITS["public_id"], errors) or ""
        self.secure_url = _normalize_public_media_url(self.secure_url, "secure_url", errors, required=False) or ""
        self.caption = _normalize_optional_text(self.caption, "caption", TEXT_LIMITS["caption"], errors)
        self.media_type = _normalize_enum_value(PortfolioMediaType, self.media_type, "media_type", errors)
        self.upload_status = _normalize_enum_value(
            PortfolioUploadStatus,
            self.upload_status,
            "upload_status",
            errors,
        )
        self.quality_status = _normalize_enum_value(
            PortfolioQualityStatus,
            self.quality_status,
            "quality_status",
            errors,
        )
        self.visibility_status = _normalize_enum_value(
            PortfolioVisibilityStatus,
            self.visibility_status,
            "visibility_status",
            errors,
        )
        self.cloudinary_public_id = _normalize_optional_text(
            self.cloudinary_public_id,
            "cloudinary_public_id",
            TEXT_LIMITS["public_id"],
            errors,
        )
        self.cloudinary_secure_url = _normalize_public_media_url(
            self.cloudinary_secure_url,
            "cloudinary_secure_url",
            errors,
            required=False,
        )
        self.rejection_reason = _normalize_optional_text(
            self.rejection_reason,
            "rejection_reason",
            TEXT_LIMITS["rejection_reason"],
            errors,
        )
        self.upload_error = _normalize_optional_text(self.upload_error, "upload_error", 1000, errors)
        self.failure_reason = _normalize_optional_text(self.failure_reason, "failure_reason", 1000, errors)
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        self.updated_at = _normalize_datetime(self.updated_at, "updated_at", errors, required=True)
        self.deleted_at = _normalize_datetime(self.deleted_at, "deleted_at", errors)

        if not isinstance(self.order, int) or self.order < 0 or self.order > MAX_PORTFOLIO_ORDER:
            add_error(errors, "order", f"Order must be between 0 and {MAX_PORTFOLIO_ORDER}.")
        if self.file_size < 0:
            add_error(errors, "file_size", "File size cannot be negative.")
        _validate_public_id_url_pair(
            errors,
            url=self.secure_url or None,
            public_id=self.public_id or None,
            url_field="secure_url",
            public_id_field="public_id",
        )
        _validate_public_id_url_pair(
            errors,
            url=self.cloudinary_secure_url,
            public_id=self.cloudinary_public_id,
            url_field="cloudinary_secure_url",
            public_id_field="cloudinary_public_id",
        )
        if self.visibility_status == PortfolioVisibilityStatus.APPROVED.value:
            if (
                not self.is_active
                or self.is_deleted
                or self.upload_status != PortfolioUploadStatus.UPLOADED.value
                or self.quality_status != PortfolioQualityStatus.PASSED.value
                or not (self.cloudinary_secure_url or self.secure_url)
            ):
                add_error(errors, "visibility_status", "Approved media must be active, uploaded, passed, and public.")
        if (
            self.upload_status == PortfolioUploadStatus.FAILED.value
            and self.visibility_status != PortfolioVisibilityStatus.PRIVATE.value
        ):
            add_error(errors, "visibility_status", "Failed uploads must remain private.")
        if self.is_deleted and self.is_active:
            add_error(errors, "is_active", "Deleted media must be inactive.")
        if self.is_deleted and self.visibility_status == PortfolioVisibilityStatus.APPROVED.value:
            add_error(errors, "visibility_status", "Deleted media cannot be public.")

        if errors:
            raise PortfolioValidationError(field_errors=errors)

    def attach_cloudinary_asset(self, *, public_id: str, secure_url: str) -> None:
        candidate = replace(
            self,
            public_id=public_id,
            secure_url=secure_url,
            cloudinary_public_id=public_id,
            cloudinary_secure_url=secure_url,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_queued(self) -> None:
        candidate = replace(
            self,
            upload_status=PortfolioUploadStatus.QUEUED.value,
            quality_status=PortfolioQualityStatus.PENDING_ANALYSIS.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=None,
            failure_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_processing(self) -> None:
        candidate = replace(
            self,
            upload_status=PortfolioUploadStatus.PROCESSING.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_uploaded(
        self,
        *,
        public_id: str | None = None,
        secure_url: str | None = None,
        quality_status: str = PortfolioQualityStatus.PASSED.value,
    ) -> None:
        candidate = replace(
            self,
            public_id=public_id if public_id is not None else self.public_id,
            secure_url=secure_url if secure_url is not None else self.secure_url,
            cloudinary_public_id=public_id if public_id is not None else self.cloudinary_public_id,
            cloudinary_secure_url=secure_url if secure_url is not None else self.cloudinary_secure_url,
            upload_status=PortfolioUploadStatus.UPLOADED.value,
            quality_status=quality_status,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=None,
            failure_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_failed(self, reason: str) -> None:
        clean_reason = _validated_transition_reason(reason, "failure_reason", PortfolioValidationError)
        candidate = replace(
            self,
            upload_status=PortfolioUploadStatus.FAILED.value,
            quality_status=PortfolioQualityStatus.FAILED.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=clean_reason,
            failure_reason=clean_reason,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def submit_for_approval(self) -> None:
        if (
            self.upload_status != PortfolioUploadStatus.UPLOADED.value
            or self.quality_status != PortfolioQualityStatus.PASSED.value
            or not self.is_active
            or self.is_deleted
        ):
            raise InvalidPortfolioTransition("Only active uploaded media that passed quality review can be submitted.")
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.WAITING_APPROVAL.value,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def approve(self) -> None:
        if self.visibility_status != PortfolioVisibilityStatus.WAITING_APPROVAL.value:
            raise InvalidPortfolioTransition("Only waiting portfolio media can be approved.")
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.APPROVED.value,
            rejection_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def reject(self, reason: str) -> None:
        clean_reason = _validated_transition_reason(reason, "rejection_reason", PortfolioValidationError)
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.REJECTED.value,
            rejection_reason=clean_reason,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def deactivate(self) -> None:
        if self.is_deleted and not self.is_active:
            return
        candidate = replace(
            self,
            is_active=False,
            is_deleted=True,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            deleted_at=utc_now(),
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def reorder(self, new_order: int) -> None:
        candidate = replace(self, order=new_order, updated_at=utc_now())
        self._assign(candidate)

    def update_caption(self, caption: Optional[str]) -> None:
        candidate = replace(self, caption=caption, updated_at=utc_now())
        self._assign(candidate)

    def _assign(self, candidate: "PortfolioImage") -> None:
        self.__dict__.update(candidate.__dict__)


@dataclass
class ServicePackage:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str = "RWF"
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
        self.validate_invariants()

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.vendor_id = _normalize_uuid(self.vendor_id, "vendor_id", errors)
        self.name = _normalize_text(self.name, "name", TEXT_LIMITS["package_name"], errors)
        self.description = _normalize_text(
            self.description,
            "description",
            TEXT_LIMITS["package_description"],
            errors,
            min_length=MIN_PACKAGE_DESCRIPTION_LENGTH,
        )
        self.price = _normalize_price(self.price, errors)
        self.currency = _normalize_currency_value(self.currency, errors)
        self.package_tier = _normalize_enum_value(PackageTier, self.package_tier, "package_tier", errors)
        self.approval_status = _normalize_enum_value(
            PackageApprovalStatus,
            self.approval_status,
            "approval_status",
            errors,
        )
        self.rejection_reason = _normalize_optional_text(
            self.rejection_reason,
            "rejection_reason",
            TEXT_LIMITS["rejection_reason"],
            errors,
        )
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        self.updated_at = _normalize_datetime(self.updated_at, "updated_at", errors, required=True)
        self.deleted_at = _normalize_datetime(self.deleted_at, "deleted_at", errors)
        self.last_approved_at = _normalize_datetime(self.last_approved_at, "last_approved_at", errors)
        self.last_vendor_public_edit_at = _normalize_datetime(
            self.last_vendor_public_edit_at,
            "last_vendor_public_edit_at",
            errors,
        )
        self.next_vendor_edit_allowed_at = _normalize_datetime(
            self.next_vendor_edit_allowed_at,
            "next_vendor_edit_allowed_at",
            errors,
        )

        if self.is_deleted and self.is_active:
            add_error(errors, "is_active", "Deleted packages must be inactive.")
        if self.is_deleted and self.deleted_at is None:
            self.deleted_at = self.updated_at
        if self.approval_status == PackageApprovalStatus.REJECTED.value:
            if self.is_active:
                add_error(errors, "is_active", "Rejected packages cannot be active.")
        if self.approval_status != PackageApprovalStatus.REJECTED.value and self.rejection_reason:
            add_error(errors, "rejection_reason", "Only rejected packages can have rejection metadata.")
        if self.last_vendor_public_edit_at and self.next_vendor_edit_allowed_at:
            if self.next_vendor_edit_allowed_at < self.last_vendor_public_edit_at:
                add_error(errors, "next_vendor_edit_allowed_at", "Next edit time cannot be before the last edit.")

        if errors:
            raise PackageValidationError(field_errors=errors)

    def update_details(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[Decimal] = None,
        currency: Optional[str] = None,
        package_tier: Optional[str] = None,
    ) -> None:
        candidate = replace(
            self,
            name=self.name if name is None else name,
            description=self.description if description is None else description,
            price=self.price if price is None else price,
            currency=self.currency if currency is None else currency,
            package_tier=self.package_tier if package_tier is None else package_tier,
            approval_status=(
                PackageApprovalStatus.WAITING_APPROVAL.value
                if self.approval_status == PackageApprovalStatus.APPROVED.value
                else self.approval_status
            ),
            rejection_reason=(
                None
                if self.approval_status == PackageApprovalStatus.REJECTED.value
                else self.rejection_reason
            ),
            is_active=False if self.approval_status == PackageApprovalStatus.APPROVED.value else self.is_active,
            updated_at=utc_now(),
        )
        self.__dict__.update(candidate.__dict__)

    def deactivate(self) -> None:
        if self.is_deleted and not self.is_active:
            return
        candidate = replace(
            self,
            is_active=False,
            is_deleted=True,
            deleted_at=utc_now(),
            updated_at=utc_now(),
        )
        self.__dict__.update(candidate.__dict__)

    def activate(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be activated.")
        if self.approval_status != PackageApprovalStatus.APPROVED.value:
            raise InvalidPackageTransition("Only approved packages can be activated.")
        candidate = replace(self, is_active=True, updated_at=utc_now())
        self.__dict__.update(candidate.__dict__)


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

    def __post_init__(self) -> None:
        self.validate_invariants()

    @classmethod
    def create(
        cls,
        *,
        vendor_id: uuid.UUID,
        client_name: str,
        client_email: str,
        message: str,
        client_phone: Optional[str] = None,
        event_date: Optional[datetime] = None,
    ) -> "Inquiry":
        return cls(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            client_name=client_name,
            client_email=client_email,
            message=message,
            client_phone=client_phone,
            event_date=event_date,
        )

    def validate_invariants(self) -> None:
        errors: dict[str, list[str]] = {}
        self.id = _normalize_uuid(self.id, "id", errors)
        self.vendor_id = _normalize_uuid(self.vendor_id, "vendor_id", errors)
        self.client_name = _normalize_text(
            self.client_name,
            "client_name",
            TEXT_LIMITS["client_name"],
            errors,
        )
        self.client_email = _normalize_email(self.client_email, "client_email", errors)
        self.client_phone = _normalize_optional_phone(self.client_phone, "client_phone", errors)
        self.message = _normalize_text(
            self.message,
            "message",
            TEXT_LIMITS["message"],
            errors,
            min_length=MIN_INQUIRY_MESSAGE_LENGTH,
        )
        self.event_date = _normalize_datetime(self.event_date, "event_date", errors)
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        if errors:
            raise InquiryValidationError(field_errors=errors)

    def mark_read(self) -> None:
        self.is_read = True


def _normalize_uuid(value, field_name: str, errors: dict[str, list[str]]) -> uuid.UUID:
    try:
        return validate_uuid(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_text(
    value,
    field_name: str,
    max_length: int,
    errors: dict[str, list[str]],
    *,
    min_length: int = 1,
) -> str:
    try:
        return bounded_text(value, field_name=field_name, max_length=max_length, min_length=min_length)
    except ValueError as exc:
        if field_name == "name" and str(exc) == "This field is required.":
            add_error(errors, field_name, "Package name is required.")
        else:
            add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)


def _normalize_optional_text(
    value,
    field_name: str,
    max_length: int,
    errors: dict[str, list[str]],
) -> str | None:
    try:
        return bounded_text(value, field_name=field_name, max_length=max_length, required=False)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_email(value, field_name: str, errors: dict[str, list[str]]) -> str:
    try:
        return validate_email(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)


def _normalize_phone(value, field_name: str, errors: dict[str, list[str]]) -> str:
    try:
        return normalize_phone(value)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return "" if value is None else str(value)


def _normalize_optional_phone(value, field_name: str, errors: dict[str, list[str]]) -> str | None:
    try:
        return normalize_phone(value, required=False)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_safe_url(value, field_name: str, errors: dict[str, list[str]]) -> str | None:
    try:
        return validate_safe_url(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_public_media_url(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    required: bool = False,
) -> str | None:
    try:
        return validate_public_media_url(value, field_name=field_name, required=required)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_datetime(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    required: bool = False,
) -> datetime | None:
    try:
        return aware_utc_datetime(value, field_name=field_name, required=required)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_price(value, errors: dict[str, list[str]]) -> Decimal:
    try:
        return positive_decimal(value)
    except ValueError as exc:
        add_error(errors, "price", str(exc))
        try:
            return coerce_package_price(value)
        except ValueError:
            return Decimal("0")


def _normalize_currency_value(value, errors: dict[str, list[str]]) -> str:
    try:
        return normalize_currency(value)
    except ValueError as exc:
        add_error(errors, "currency", str(exc))
        return "" if value is None else str(value)


def _normalize_enum(enum_cls, value, field_name: str, errors: dict[str, list[str]]):
    try:
        return value if isinstance(value, enum_cls) else enum_cls(value)
    except ValueError:
        add_error(errors, field_name, f"Choose a valid {field_name}.")
        return value


def _normalize_enum_value(enum_cls, value, field_name: str, errors: dict[str, list[str]]) -> str:
    enum_value = _normalize_enum(enum_cls, value, field_name, errors)
    return enum_value.value if isinstance(enum_value, enum_cls) else value


def _validate_public_id_url_pair(
    errors: dict[str, list[str]],
    *,
    url: str | None,
    public_id: str | None,
    url_field: str,
    public_id_field: str,
) -> None:
    if bool(url) != bool(public_id):
        add_error(errors, public_id_field if url else url_field, "Public ID and URL must be stored together.")


def _validated_transition_reason(reason: str, field_name: str, error_cls):
    errors: dict[str, list[str]] = {}
    clean_reason = _normalize_text(reason, field_name, TEXT_LIMITS["rejection_reason"], errors)
    if errors:
        raise error_cls(field_errors=errors)
    return clean_reason
