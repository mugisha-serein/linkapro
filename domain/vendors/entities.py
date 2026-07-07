from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from domain.shared.utils import utc_now
from domain.vendors.events import (
    InquiryRead,
    InquiryReceived,
    PortfolioCaptionUpdated,
    PortfolioMediaApproved,
    PortfolioMediaDeactivated,
    PortfolioMediaFailed,
    PortfolioMediaProcessingStarted,
    PortfolioMediaQueued,
    PortfolioMediaRejected,
    PortfolioMediaReordered,
    PortfolioMediaSubmittedForApproval,
    PortfolioMediaUploaded,
    ServicePackageActivated,
    ServicePackageApproved,
    ServicePackageCreated,
    ServicePackageDeactivated,
    ServicePackageRejected,
    ServicePackageSubmittedForApproval,
    ServicePackageUpdated,
    VendorApproved,
    VendorRejected,
    VendorReinstated,
    VendorSubmittedForReview,
    VendorSuspended,
)
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
from domain.vendors.package_rules import validate_service_package_rules
from domain.vendors.package_edit_policy import mark_vendor_package_public_edit, package_public_fields_changed
from domain.vendors.validation import (
    MAX_PORTFOLIO_DIMENSION,
    MAX_PORTFOLIO_FILE_SIZE,
    MAX_PORTFOLIO_ORDER,
    MAX_VIDEO_DURATION_SECONDS,
    MIN_INQUIRY_MESSAGE_LENGTH,
    MIN_VENDOR_DESCRIPTION_LENGTH,
    TEXT_LIMITS,
    add_error,
    aware_utc_datetime,
    bounded_text,
    normalize_currency,
    normalize_event_date,
    normalize_phone,
    positive_decimal,
    validate_new_event_date_bounds,
    validate_bool,
    validate_email,
    validate_int,
    validate_optional_int,
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


@dataclass(frozen=True)
class MediaAsset:
    public_id: str
    secure_url: str

    def __post_init__(self) -> None:
        errors: dict[str, list[str]] = {}
        public_id = _normalize_text(self.public_id, "public_id", TEXT_LIMITS["public_id"], errors)
        secure_url = _normalize_public_media_url(self.secure_url, "secure_url", errors, required=True)
        if errors:
            raise PortfolioValidationError(field_errors=errors)
        object.__setattr__(self, "public_id", public_id)
        object.__setattr__(self, "secure_url", secure_url)


class DomainAggregate:
    version: int
    _events: list

    def _init_domain_state(self) -> None:
        if not hasattr(self, "_events") or self._events is None:
            self._events = []

    def _record(self, event) -> None:
        self._events.append(event)

    def pull_events(self) -> list:
        events = list(self._events)
        self._events.clear()
        return events

    def _bump_version(self) -> None:
        self.version += 1

    def _commit_candidate(self, candidate, event=None) -> None:
        candidate.validate_invariants()
        pending_events = list(self._events)
        for key, value in candidate.__dict__.items():
            if key != "_events":
                setattr(self, key, value)
        self._events = pending_events
        self._bump_version()
        if event is not None:
            self._record(event)


@dataclass
class VendorProfile(DomainAggregate):
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
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
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
        cls._validate_rehydrate_input(kwargs)
        profile = cls(**kwargs)
        profile._validate_strict_rehydration()
        profile._events.clear()
        return profile

    @classmethod
    def _validate_rehydrate_input(cls, kwargs: dict) -> None:
        status = kwargs.get("status", VendorStatus.DRAFT)
        if isinstance(status, VendorStatus):
            status_value = status.value
        else:
            status_value = status
        errors: dict[str, list[str]] = {}
        if status_value == VendorStatus.PENDING_REVIEW.value and kwargs.get("submitted_at") is None:
            add_error(errors, "submitted_at", "Pending vendors require submitted_at.")
        if status_value == VendorStatus.APPROVED.value and kwargs.get("approved_at") is None:
            add_error(errors, "approved_at", "Approved vendors require approved_at.")
        if status_value == VendorStatus.REJECTED.value:
            if kwargs.get("rejected_at") is None:
                add_error(errors, "rejected_at", "Rejected vendors require rejected_at.")
            if not kwargs.get("rejection_reason"):
                add_error(errors, "rejection_reason", "Rejected vendors require rejection_reason.")
        if errors:
            raise VendorProfileValidationError(field_errors=errors)

    def _validate_strict_rehydration(self) -> None:
        errors: dict[str, list[str]] = {}
        if self.status == VendorStatus.PENDING_REVIEW and self.submitted_at is None:
            add_error(errors, "submitted_at", "Pending vendors require submitted_at.")
        if self.status == VendorStatus.APPROVED and self.approved_at is None:
            add_error(errors, "approved_at", "Approved vendors require approved_at.")
        if self.status == VendorStatus.REJECTED and self.rejected_at is None:
            add_error(errors, "rejected_at", "Rejected vendors require rejected_at.")
        if self.submitted_at and self.approved_at and self.approved_at < self.submitted_at:
            add_error(errors, "approved_at", "Approval cannot happen before submission.")
        if self.submitted_at and self.rejected_at and self.rejected_at < self.submitted_at:
            add_error(errors, "rejected_at", "Rejection cannot happen before submission.")
        if errors:
            raise VendorProfileValidationError(field_errors=errors)

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
        self.version = _normalize_version(self.version, errors)

        if self.category == ServiceCategory.OTHER and not self.custom_category:
            add_error(errors, "custom_category", "Tell us what service you provide when choosing Other.")
        if self.category != ServiceCategory.OTHER and self.custom_category:
            add_error(errors, "custom_category", "Custom category is only allowed when category is Other.")
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
        if self.status == VendorStatus.DRAFT:
            if self.submitted_at is not None:
                add_error(errors, "submitted_at", "Draft vendors cannot have submission metadata.")
            if self.approved_at is not None:
                add_error(errors, "approved_at", "Draft vendors cannot have approval metadata.")
            if self.rejected_at is not None:
                add_error(errors, "rejected_at", "Draft vendors cannot have rejection metadata.")
        if self.status == VendorStatus.PENDING_REVIEW:
            if self.submitted_at is None:
                add_error(errors, "submitted_at", "Pending vendors require submitted_at.")
            if self.approved_at is not None:
                add_error(errors, "approved_at", "Pending vendors cannot have approval metadata.")
            if self.rejected_at is not None:
                add_error(errors, "rejected_at", "Pending vendors cannot have rejection metadata.")
        if self.status == VendorStatus.APPROVED:
            if self.submitted_at is None:
                add_error(errors, "submitted_at", "Approved vendors require submitted_at.")
            if self.approved_at is None:
                add_error(errors, "approved_at", "Approved vendors require approved_at.")
            if self.rejected_at is not None:
                add_error(errors, "rejected_at", "Approved vendors cannot have rejection metadata.")
        if self.status == VendorStatus.REJECTED:
            if self.submitted_at is None:
                add_error(errors, "submitted_at", "Rejected vendors require submitted_at.")
            if not self.rejection_reason:
                add_error(errors, "rejection_reason", "Rejection reason is required.")
            if self.rejected_at is None:
                add_error(errors, "rejected_at", "Rejected vendors require rejected_at.")
            if self.approved_at is not None:
                add_error(errors, "approved_at", "Rejected vendors cannot have approval metadata.")
        if self.status == VendorStatus.SUSPENDED:
            if self.submitted_at is None:
                add_error(errors, "submitted_at", "Suspended vendors require submitted_at.")
            if self.approved_at is None:
                add_error(errors, "approved_at", "Suspended vendors require previous approval metadata.")
            if self.rejected_at is not None:
                add_error(errors, "rejected_at", "Suspended vendors cannot have rejection metadata.")
        if self.status != VendorStatus.REJECTED and self.rejection_reason:
            add_error(errors, "rejection_reason", "Only rejected vendors can have rejection metadata.")
        if self.submitted_at and self.submitted_at < self.created_at:
            add_error(errors, "submitted_at", "Submission cannot happen before creation.")
        if self.approved_at and self.submitted_at and self.approved_at < self.submitted_at:
            add_error(errors, "approved_at", "Approval cannot happen before submission.")
        if self.rejected_at and self.submitted_at and self.rejected_at < self.submitted_at:
            add_error(errors, "rejected_at", "Rejection cannot happen before submission.")
        for field_name in ("submitted_at", "approved_at", "rejected_at"):
            value = getattr(self, field_name)
            if value and self.updated_at and value > self.updated_at:
                add_error(errors, field_name, "Lifecycle timestamp cannot be after updated_at.")
        if self.description and len(self.description) < MIN_VENDOR_DESCRIPTION_LENGTH:
            add_error(errors, "description", "Use at least 20 characters for your description.")
        if self.created_at and self.updated_at and self.updated_at < self.created_at:
            add_error(errors, "updated_at", "Updated timestamp cannot be before creation.")

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
        if self.description and len(self.description.strip()) < MIN_VENDOR_DESCRIPTION_LENGTH:
            errors["description"] = ["Use at least 20 characters for your description."]
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
        candidate = replace(
            self,
            status=VendorStatus.PENDING_REVIEW,
            submitted_at=now,
            approved_at=None,
            rejected_at=None,
            rejection_reason=None,
            updated_at=now,
        )
        self._commit_candidate(
            candidate,
            VendorSubmittedForReview(vendor_id=self.id, user_id=self.user_id, occurred_at=now),
        )

    def approve(self) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise InvalidVendorTransition("Only pending profiles can be approved")
        now = utc_now()
        candidate = replace(
            self,
            status=VendorStatus.APPROVED,
            approved_at=now,
            rejected_at=None,
            rejection_reason=None,
            updated_at=now,
        )
        self._commit_candidate(candidate, VendorApproved(vendor_id=self.id, occurred_at=now))

    def reject(self, reason: str) -> None:
        if self.status != VendorStatus.PENDING_REVIEW:
            raise InvalidVendorTransition("Only pending profiles can be rejected")
        clean_reason = _validated_transition_reason(reason, "rejection_reason", VendorProfileValidationError)
        now = utc_now()
        candidate = replace(
            self,
            status=VendorStatus.REJECTED,
            approved_at=None,
            rejected_at=now,
            rejection_reason=clean_reason,
            updated_at=now,
        )
        self._commit_candidate(
            candidate,
            VendorRejected(vendor_id=self.id, reason=clean_reason, occurred_at=now),
        )

    def suspend(self, reason: str | None = None) -> None:
        if self.status != VendorStatus.APPROVED:
            raise InvalidVendorTransition("Only approved vendors can be suspended")
        if reason is not None:
            reason = _validated_transition_reason(reason, "reason", VendorProfileValidationError)
        now = utc_now()
        candidate = replace(self, status=VendorStatus.SUSPENDED, updated_at=now)
        self._commit_candidate(candidate, VendorSuspended(vendor_id=self.id, reason=reason, occurred_at=now))

    def reinstate(self) -> None:
        if self.status != VendorStatus.SUSPENDED:
            raise InvalidVendorTransition("Only suspended vendors can be reinstated")
        now = utc_now()
        candidate = replace(self, status=VendorStatus.APPROVED, updated_at=now)
        self._commit_candidate(candidate, VendorReinstated(vendor_id=self.id, occurred_at=now))


@dataclass
class PortfolioImage(DomainAggregate):
    id: uuid.UUID
    vendor_id: uuid.UUID
    public_id: str = ""
    secure_url: str = ""
    caption: Optional[str] = None
    order: int = 0
    media_type: str = "image"
    upload_status: str = "staged"
    quality_status: str = "pending_analysis"
    visibility_status: str = "private"
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
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
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
        self.version = _normalize_version(self.version, errors)
        self.is_active = _normalize_bool(self.is_active, "is_active", errors)
        self.is_deleted = _normalize_bool(self.is_deleted, "is_deleted", errors)
        self.file_size = _normalize_int(self.file_size, "file_size", errors, minimum=0)
        self.width = _normalize_optional_int(self.width, "width", errors, minimum=1, maximum=MAX_PORTFOLIO_DIMENSION)
        self.height = _normalize_optional_int(self.height, "height", errors, minimum=1, maximum=MAX_PORTFOLIO_DIMENSION)
        self.duration_seconds = _normalize_optional_int(
            self.duration_seconds,
            "duration_seconds",
            errors,
            minimum=0,
            maximum=MAX_VIDEO_DURATION_SECONDS,
        )
        self.analyzer_score = _normalize_optional_int(self.analyzer_score, "analyzer_score", errors, minimum=0, maximum=100)
        self.original_filename = _normalize_optional_text(self.original_filename, "original_filename", 255, errors)
        self.mime_type = _normalize_optional_text(self.mime_type, "mime_type", 100, errors) or ""
        self.local_preview_url = _normalize_safe_url(self.local_preview_url, "local_preview_url", errors)
        self.analyzer_summary = _normalize_optional_text(self.analyzer_summary, "analyzer_summary", 2000, errors)

        self.order = _normalize_int(self.order, "order", errors, minimum=0, maximum=MAX_PORTFOLIO_ORDER)
        if self.file_size > MAX_PORTFOLIO_FILE_SIZE:
            add_error(errors, "file_size", f"File size must be no more than {MAX_PORTFOLIO_FILE_SIZE} bytes.")
        if self.mime_type and self.mime_type not in {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime"}:
            add_error(errors, "mime_type", "Unsupported portfolio media MIME type.")
        if self.mime_type:
            if self.media_type == PortfolioMediaType.IMAGE.value and not self.mime_type.startswith("image/"):
                add_error(errors, "mime_type", "Image media must use an image MIME type.")
            if self.media_type == PortfolioMediaType.VIDEO.value and not self.mime_type.startswith("video/"):
                add_error(errors, "mime_type", "Video media must use a video MIME type.")
        if self.media_type == PortfolioMediaType.IMAGE.value and self.duration_seconds:
            add_error(errors, "duration_seconds", "Image media cannot have duration.")
        _validate_public_id_url_pair(
            errors,
            url=self.secure_url or None,
            public_id=self.public_id or None,
            url_field="secure_url",
            public_id_field="public_id",
        )
        if self.public_id and self.cloudinary_public_id and self.public_id != self.cloudinary_public_id:
            add_error(errors, "cloudinary_public_id", "Legacy and Cloudinary public IDs must match.")
        if self.secure_url and self.cloudinary_secure_url and self.secure_url != self.cloudinary_secure_url:
            add_error(errors, "cloudinary_secure_url", "Legacy and Cloudinary secure URLs must match.")
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
        if self.is_deleted and self.deleted_at is None:
            add_error(errors, "deleted_at", "Deleted media require deleted_at.")

        if errors:
            raise PortfolioValidationError(field_errors=errors)

    def attach_cloudinary_asset(self, *, public_id: str, secure_url: str) -> None:
        self._ensure_mutable()
        asset = MediaAsset(public_id=public_id, secure_url=secure_url)
        candidate = replace(
            self,
            public_id=asset.public_id,
            secure_url=asset.secure_url,
            cloudinary_public_id=asset.public_id,
            cloudinary_secure_url=asset.secure_url,
            quality_status=(
                self.quality_status
                if self.upload_status in {PortfolioUploadStatus.QUEUED.value, PortfolioUploadStatus.PROCESSING.value}
                else PortfolioQualityStatus.PENDING_ANALYSIS.value
            ),
            visibility_status=(
                self.visibility_status
                if self.upload_status in {PortfolioUploadStatus.QUEUED.value, PortfolioUploadStatus.PROCESSING.value}
                else PortfolioVisibilityStatus.PRIVATE.value
            ),
            rejection_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_queued(self) -> None:
        self._ensure_mutable()
        if self.upload_status != PortfolioUploadStatus.STAGED.value:
            raise InvalidPortfolioTransition("Only staged media can be queued.")
        candidate = replace(
            self,
            upload_status=PortfolioUploadStatus.QUEUED.value,
            quality_status=PortfolioQualityStatus.PENDING_ANALYSIS.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=None,
            failure_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate, PortfolioMediaQueued(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at))

    def mark_processing(self) -> None:
        self._ensure_mutable()
        if self.upload_status not in {PortfolioUploadStatus.QUEUED.value, PortfolioUploadStatus.PROCESSING_DEFERRED.value}:
            raise InvalidPortfolioTransition("Only queued media can start processing.")
        candidate = replace(
            self,
            upload_status=PortfolioUploadStatus.PROCESSING.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            updated_at=utc_now(),
        )
        self._assign(
            candidate,
            PortfolioMediaProcessingStarted(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

    def mark_uploaded(
        self,
        *,
        public_id: str | None = None,
        secure_url: str | None = None,
    ) -> None:
        self._ensure_mutable()
        if self.upload_status != PortfolioUploadStatus.PROCESSING.value:
            raise InvalidPortfolioTransition("Only processing media can be marked uploaded.")
        if public_id is None or secure_url is None:
            raise PortfolioValidationError(field_errors={"secure_url": ["Uploaded media requires a valid asset."]})
        asset = MediaAsset(public_id=public_id, secure_url=secure_url)
        candidate = replace(
            self,
            public_id=asset.public_id,
            secure_url=asset.secure_url,
            cloudinary_public_id=asset.public_id,
            cloudinary_secure_url=asset.secure_url,
            upload_status=PortfolioUploadStatus.UPLOADED.value,
            quality_status=PortfolioQualityStatus.PENDING_ANALYSIS.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=None,
            failure_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate, PortfolioMediaUploaded(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at))

    def mark_quality_passed(self) -> None:
        self._ensure_mutable()
        if self.upload_status != PortfolioUploadStatus.UPLOADED.value:
            raise InvalidPortfolioTransition("Only uploaded media can pass quality review.")
        candidate = replace(
            self,
            quality_status=PortfolioQualityStatus.PASSED.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=None,
            failure_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_quality_failed(self, reason: str) -> None:
        self._ensure_mutable()
        if self.upload_status != PortfolioUploadStatus.UPLOADED.value:
            raise InvalidPortfolioTransition("Only uploaded media can fail quality review.")
        clean_reason = _validated_transition_reason(reason, "failure_reason", PortfolioValidationError)
        candidate = replace(
            self,
            quality_status=PortfolioQualityStatus.FAILED.value,
            visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
            upload_error=clean_reason,
            failure_reason=clean_reason,
            updated_at=utc_now(),
        )
        self._assign(candidate)

    def mark_failed(self, reason: str) -> None:
        self._ensure_mutable()
        if self.upload_status not in {
            PortfolioUploadStatus.PROCESSING.value,
            PortfolioUploadStatus.PROCESSING_DEFERRED.value,
        }:
            raise InvalidPortfolioTransition("Only processing media can fail.")
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
        self._assign(
            candidate,
            PortfolioMediaFailed(
                image_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
            ),
        )

    def submit_for_approval(self) -> None:
        self._ensure_mutable()
        if (
            self.upload_status != PortfolioUploadStatus.UPLOADED.value
            or self.quality_status != PortfolioQualityStatus.PASSED.value
            or self.visibility_status != PortfolioVisibilityStatus.PRIVATE.value
            or not self.is_active
            or self.is_deleted
        ):
            raise InvalidPortfolioTransition("Only active uploaded media that passed quality review can be submitted.")
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.WAITING_APPROVAL.value,
            updated_at=utc_now(),
        )
        self._assign(
            candidate,
            PortfolioMediaSubmittedForApproval(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

    def approve(self) -> None:
        self._ensure_mutable()
        if self.visibility_status != PortfolioVisibilityStatus.WAITING_APPROVAL.value:
            raise InvalidPortfolioTransition("Only waiting portfolio media can be approved.")
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.APPROVED.value,
            rejection_reason=None,
            updated_at=utc_now(),
        )
        self._assign(candidate, PortfolioMediaApproved(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at))

    def reject(self, reason: str) -> None:
        self._ensure_mutable()
        if self.visibility_status != PortfolioVisibilityStatus.WAITING_APPROVAL.value:
            raise InvalidPortfolioTransition("Only waiting portfolio media can be rejected.")
        clean_reason = _validated_transition_reason(reason, "rejection_reason", PortfolioValidationError)
        candidate = replace(
            self,
            visibility_status=PortfolioVisibilityStatus.REJECTED.value,
            rejection_reason=clean_reason,
            updated_at=utc_now(),
        )
        self._assign(
            candidate,
            PortfolioMediaRejected(
                image_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
            ),
        )

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
        self._assign(candidate, PortfolioMediaDeactivated(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at))

    def reorder(self, new_order: int) -> None:
        self._ensure_mutable()
        candidate = replace(self, order=new_order, updated_at=utc_now())
        self._assign(
            candidate,
            PortfolioMediaReordered(image_id=self.id, vendor_id=self.vendor_id, order=candidate.order, occurred_at=candidate.updated_at),
        )

    def update_caption(self, caption: Optional[str]) -> None:
        self._ensure_mutable()
        if caption == self.caption:
            return
        candidate = replace(
            self,
            caption=caption,
            visibility_status=(
                PortfolioVisibilityStatus.WAITING_APPROVAL.value
                if self.visibility_status == PortfolioVisibilityStatus.APPROVED.value
                else self.visibility_status
            ),
            updated_at=utc_now(),
        )
        self._assign(candidate, PortfolioCaptionUpdated(image_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at))

    def _assign(self, candidate: "PortfolioImage", event=None) -> None:
        self._commit_candidate(candidate, event)

    def _ensure_mutable(self) -> None:
        if self.is_deleted:
            raise InvalidPortfolioTransition("Deleted portfolio media cannot be changed.")


@dataclass
class ServicePackage(DomainAggregate):
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str = "RWF"
    package_tier: str = "standard"
    approval_status: str = "waiting_approval"
    rejection_reason: Optional[str] = None
    is_active: bool = False
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    last_approved_at: Optional[datetime] = None
    last_vendor_public_edit_at: Optional[datetime] = None
    next_vendor_edit_allowed_at: Optional[datetime] = None
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
        self.validate_invariants()

    @classmethod
    def create(
        cls,
        *,
        vendor_id: uuid.UUID,
        name: str,
        description: str,
        price: Decimal,
        currency: str = "RWF",
        package_tier: str = PackageTier.STANDARD.value,
    ) -> "ServicePackage":
        package = cls(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            name=name,
            description=description,
            price=price,
            currency=currency,
            package_tier=package_tier,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            is_active=False,
        )
        package._record(ServicePackageCreated(package_id=package.id, vendor_id=package.vendor_id, occurred_at=package.created_at))
        return package

    @classmethod
    def rehydrate(cls, **kwargs) -> "ServicePackage":
        cls._validate_rehydrate_input(kwargs)
        package = cls(**kwargs)
        package._validate_strict_rehydration()
        package._events.clear()
        return package

    @classmethod
    def _validate_rehydrate_input(cls, kwargs: dict) -> None:
        errors: dict[str, list[str]] = {}
        approval_status = kwargs.get("approval_status", PackageApprovalStatus.WAITING_APPROVAL.value)
        if isinstance(approval_status, PackageApprovalStatus):
            approval_status = approval_status.value
        if approval_status == PackageApprovalStatus.APPROVED.value and kwargs.get("last_approved_at") is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if kwargs.get("is_deleted") is True and kwargs.get("deleted_at") is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if errors:
            raise PackageValidationError(field_errors=errors)

    def _validate_strict_rehydration(self) -> None:
        errors: dict[str, list[str]] = {}
        if self.approval_status == PackageApprovalStatus.APPROVED.value and self.last_approved_at is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if self.is_deleted and self.deleted_at is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if errors:
            raise PackageValidationError(field_errors=errors)

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
        self.version = _normalize_version(self.version, errors)
        self.is_active = _normalize_bool(self.is_active, "is_active", errors)
        self.is_deleted = _normalize_bool(self.is_deleted, "is_deleted", errors)

        if self.is_deleted and self.is_active:
            add_error(errors, "is_active", "Deleted packages must be inactive.")
        if self.is_deleted and self.deleted_at is None:
            add_error(errors, "deleted_at", "Deleted packages require deleted_at.")
        if self.approval_status == PackageApprovalStatus.APPROVED.value and self.last_approved_at is None:
            add_error(errors, "last_approved_at", "Approved packages require last_approved_at.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value and self.is_active:
            add_error(errors, "is_active", "Waiting approval packages cannot be active.")
        if self.approval_status == PackageApprovalStatus.REJECTED.value:
            if self.is_active:
                add_error(errors, "is_active", "Rejected packages cannot be active.")
            if not self.rejection_reason:
                add_error(errors, "rejection_reason", "Rejected packages require rejection_reason.")
        if self.approval_status != PackageApprovalStatus.REJECTED.value and self.rejection_reason:
            add_error(errors, "rejection_reason", "Only rejected packages can have rejection metadata.")
        if self.last_vendor_public_edit_at and self.next_vendor_edit_allowed_at:
            if self.next_vendor_edit_allowed_at < self.last_vendor_public_edit_at:
                add_error(errors, "next_vendor_edit_allowed_at", "Next edit time cannot be before the last edit.")

        try:
            validate_service_package_rules(
                name=self.name,
                description=self.description,
                price=self.price,
                package_tier=self.package_tier,
            )
        except PackageValidationError as exc:
            for field_name, messages in exc.field_errors.items():
                for message in messages:
                    add_error(errors, field_name, message)

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
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be edited.")
        next_name = self.name if name is None else name
        next_description = self.description if description is None else description
        next_price = self.price if price is None else price
        next_currency = self.currency if currency is None else currency
        next_tier = self.package_tier if package_tier is None else package_tier
        public_changed = package_public_fields_changed(
            self,
            name=next_name,
            description=next_description,
            price=next_price,
            currency=next_currency,
            package_tier=next_tier,
        )
        if not public_changed:
            return
        now = utc_now()
        markers = mark_vendor_package_public_edit(self, now=now, public_fields_changed=True)
        candidate = replace(
            self,
            name=next_name,
            description=next_description,
            price=next_price,
            currency=next_currency,
            package_tier=next_tier,
            updated_at=now,
            **markers,
        )
        self._commit_candidate(
            candidate,
            ServicePackageUpdated(package_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

    def submit_for_approval(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be submitted.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value:
            return
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            rejection_reason=None,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            ServicePackageSubmittedForApproval(package_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

    def approve(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be approved.")
        if self.approval_status != PackageApprovalStatus.WAITING_APPROVAL.value:
            raise InvalidPackageTransition("Only waiting packages can be approved.")
        now = utc_now()
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.APPROVED.value,
            rejection_reason=None,
            last_approved_at=now,
            is_active=False,
            updated_at=now,
        )
        self._commit_candidate(candidate, ServicePackageApproved(package_id=self.id, vendor_id=self.vendor_id, occurred_at=now))

    def reject(self, reason: str) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be rejected.")
        if self.approval_status != PackageApprovalStatus.WAITING_APPROVAL.value:
            raise InvalidPackageTransition("Only waiting packages can be rejected.")
        clean_reason = _validated_transition_reason(reason, "rejection_reason", PackageValidationError)
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.REJECTED.value,
            rejection_reason=clean_reason,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            ServicePackageRejected(
                package_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
            ),
        )

    def restore_to_waiting_approval(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be restored.")
        if self.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value and not self.is_active:
            return
        candidate = replace(
            self,
            approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
            rejection_reason=None,
            is_active=False,
            updated_at=utc_now(),
        )
        self._commit_candidate(
            candidate,
            ServicePackageSubmittedForApproval(package_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

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
        self._commit_candidate(
            candidate,
            ServicePackageDeactivated(package_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )

    def activate(self) -> None:
        if self.is_deleted:
            raise InvalidPackageTransition("Deleted packages cannot be activated.")
        if self.approval_status != PackageApprovalStatus.APPROVED.value:
            raise InvalidPackageTransition("Only approved packages can be activated.")
        if self.is_active:
            return
        candidate = replace(self, is_active=True, updated_at=utc_now())
        self._commit_candidate(
            candidate,
            ServicePackageActivated(package_id=self.id, vendor_id=self.vendor_id, occurred_at=candidate.updated_at),
        )


@dataclass
class Inquiry(DomainAggregate):
    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    client_phone: Optional[str] = None
    event_date: Optional[date] = None
    is_read: bool = False
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    _events: list = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._init_domain_state()
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
        event_date: Optional[date] = None,
    ) -> "Inquiry":
        try:
            checked_event_date = validate_new_event_date_bounds(normalize_event_date(event_date))
        except ValueError as exc:
            raise InquiryValidationError(field_errors={"event_date": [str(exc)]}) from exc
        inquiry = cls(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            client_name=client_name,
            client_email=client_email,
            message=message,
            client_phone=client_phone,
            event_date=checked_event_date,
        )
        inquiry._record(InquiryReceived(inquiry_id=inquiry.id, vendor_id=inquiry.vendor_id, occurred_at=inquiry.created_at))
        return inquiry

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
        self.event_date = _normalize_event_date(self.event_date, "event_date", errors)
        self.is_read = _normalize_bool(self.is_read, "is_read", errors)
        self.version = _normalize_version(self.version, errors)
        self.created_at = _normalize_datetime(self.created_at, "created_at", errors, required=True)
        if errors:
            raise InquiryValidationError(field_errors=errors)

    def mark_read(self) -> None:
        if self.is_read:
            return
        now = utc_now()
        candidate = replace(self, is_read=True)
        self._commit_candidate(candidate, InquiryRead(inquiry_id=self.id, vendor_id=self.vendor_id, occurred_at=now))

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


def _normalize_event_date(value, field_name: str, errors: dict[str, list[str]]) -> date | None:
    try:
        return normalize_event_date(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_bool(value, field_name: str, errors: dict[str, list[str]]) -> bool:
    try:
        return validate_bool(value, field_name=field_name)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_int(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        return validate_int(value, field_name=field_name, minimum=minimum, maximum=maximum)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_optional_int(
    value,
    field_name: str,
    errors: dict[str, list[str]],
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    try:
        return validate_optional_int(value, field_name=field_name, minimum=minimum, maximum=maximum)
    except ValueError as exc:
        add_error(errors, field_name, str(exc))
        return value


def _normalize_version(value, errors: dict[str, list[str]]) -> int:
    try:
        return validate_int(value, field_name="version", minimum=0)
    except ValueError as exc:
        add_error(errors, "version", str(exc))
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
