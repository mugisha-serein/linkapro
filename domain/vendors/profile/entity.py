from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional

from domain.shared.utils import utc_now
from domain.vendors.profile.errors import InvalidVendorTransition, VendorProfileValidationError
from domain.vendors.profile.events import (
    VendorApproved,
    VendorProfileUpdated,
    VendorRejected,
    VendorReinstated,
    VendorSubmittedForReview,
    VendorSuspended,
)
from domain.vendors.shared.aggregate import (
    DomainAggregate,
    _UNSET,
    _normalize_datetime,
    _normalize_email,
    _normalize_enum,
    _normalize_optional_text,
    _normalize_phone,
    _normalize_public_media_url,
    _normalize_safe_url,
    _normalize_text,
    _normalize_uuid,
    _normalize_version,
    _validate_public_id_url_pair,
    _validated_transition_reason,
)
from domain.vendors.shared.validation import MIN_VENDOR_DESCRIPTION_LENGTH, TEXT_LIMITS, add_error

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

def profile_completion_errors_for(profile: object, required_fields: tuple[str, ...]) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field_name in required_fields:
        value = getattr(profile, field_name, None)
        if value is None or not str(value).strip():
            errors[field_name] = ["This field is required."]

    category = getattr(profile, "category", None)
    category_value = getattr(category, "value", category)
    if category_value == ServiceCategory.OTHER.value and not (getattr(profile, "custom_category", None) or "").strip():
        errors["custom_category"] = ["Tell us what service you provide when choosing Other."]

    description = getattr(profile, "description", None)
    if description and len(str(description).strip()) < MIN_VENDOR_DESCRIPTION_LENGTH:
        errors["description"] = ["Use at least 20 characters for your description."]
    return errors

@dataclass
class VendorProfile(DomainAggregate):
    _protected_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "status",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "version",
        }
    )

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
        self._lock_state()

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
        return profile_completion_errors_for(self, self.required_profile_fields())

    @property
    def is_profile_complete(self) -> bool:
        return not self.get_profile_completion_errors()

    def update_details(
        self,
        *,
        business_name=_UNSET,
        category=_UNSET,
        description=_UNSET,
        service_area=_UNSET,
        contact_email=_UNSET,
        contact_phone=_UNSET,
        custom_category=_UNSET,
        website=_UNSET,
        profile_image_url=_UNSET,
        profile_image_public_id=_UNSET,
        cover_image_url=_UNSET,
        cover_image_public_id=_UNSET,
    ) -> None:
        candidate = replace(
            self,
            business_name=self.business_name if business_name is _UNSET else business_name,
            category=self.category if category is _UNSET else category,
            description=self.description if description is _UNSET else description,
            service_area=self.service_area if service_area is _UNSET else service_area,
            contact_email=self.contact_email if contact_email is _UNSET else contact_email,
            contact_phone=self.contact_phone if contact_phone is _UNSET else contact_phone,
            custom_category=self.custom_category if custom_category is _UNSET else custom_category,
            website=self.website if website is _UNSET else website,
            profile_image_url=self.profile_image_url if profile_image_url is _UNSET else profile_image_url,
            profile_image_public_id=(
                self.profile_image_public_id if profile_image_public_id is _UNSET else profile_image_public_id
            ),
            cover_image_url=self.cover_image_url if cover_image_url is _UNSET else cover_image_url,
            cover_image_public_id=self.cover_image_public_id if cover_image_public_id is _UNSET else cover_image_public_id,
        )
        changed_fields = (
            "business_name",
            "category",
            "description",
            "service_area",
            "contact_email",
            "contact_phone",
            "custom_category",
            "website",
            "profile_image_url",
            "profile_image_public_id",
            "cover_image_url",
            "cover_image_public_id",
        )
        if all(getattr(candidate, field_name) == getattr(self, field_name) for field_name in changed_fields):
            return

        now = utc_now()
        candidate = replace(candidate, updated_at=now)
        self._commit_candidate(
            candidate,
            lambda version: VendorProfileUpdated(
                vendor_id=self.id,
                user_id=self.user_id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

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
            lambda version: VendorSubmittedForReview(
                vendor_id=self.id,
                user_id=self.user_id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
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
        self._commit_candidate(
            candidate,
            lambda version: VendorApproved(
                vendor_id=self.id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

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
            lambda version: VendorRejected(
                vendor_id=self.id,
                reason=clean_reason,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def suspend(self, reason: str | None = None) -> None:
        if self.status != VendorStatus.APPROVED:
            raise InvalidVendorTransition("Only approved vendors can be suspended")
        if reason is not None:
            reason = _validated_transition_reason(reason, "reason", VendorProfileValidationError)
        now = utc_now()
        candidate = replace(self, status=VendorStatus.SUSPENDED, updated_at=now)
        self._commit_candidate(
            candidate,
            lambda version: VendorSuspended(
                vendor_id=self.id,
                reason=reason,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def reinstate(self) -> None:
        if self.status != VendorStatus.SUSPENDED:
            raise InvalidVendorTransition("Only suspended vendors can be reinstated")
        now = utc_now()
        candidate = replace(self, status=VendorStatus.APPROVED, updated_at=now)
        self._commit_candidate(
            candidate,
            lambda version: VendorReinstated(
                vendor_id=self.id,
                occurred_at=now,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )
