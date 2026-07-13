from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Callable, ClassVar, Optional

from domain.shared.utils import utc_now
from domain.vendors.portfolio.errors import InvalidPortfolioTransition, PortfolioValidationError
from domain.vendors.portfolio.events import (
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
)
from domain.vendors.shared.aggregate import (
    DomainAggregate,
    _normalize_bool,
    _normalize_datetime,
    _normalize_enum_value,
    _normalize_int,
    _normalize_optional_int,
    _normalize_optional_text,
    _normalize_public_media_url,
    _normalize_safe_url,
    _normalize_text,
    _normalize_uuid,
    _normalize_version,
    _validate_public_id_url_pair,
    _validated_transition_reason,
)
from domain.vendors.shared.validation import (
    MAX_PORTFOLIO_DIMENSION,
    MAX_PORTFOLIO_FILE_SIZE,
    MAX_PORTFOLIO_ORDER,
    MAX_VIDEO_DURATION_SECONDS,
    TEXT_LIMITS,
    add_error,
)

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

@dataclass
class PortfolioImage(DomainAggregate):
    _protected_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "upload_status",
            "quality_status",
            "visibility_status",
            "is_active",
            "is_deleted",
            "deleted_at",
            "version",
        }
    )

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
        self._lock_state()

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
        self._assign(
            candidate,
            lambda version: PortfolioMediaQueued(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

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
            lambda version: PortfolioMediaProcessingStarted(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
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
        self._assign(
            candidate,
            lambda version: PortfolioMediaUploaded(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

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
            lambda version: PortfolioMediaFailed(
                image_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
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
            lambda version: PortfolioMediaSubmittedForApproval(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
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
        self._assign(
            candidate,
            lambda version: PortfolioMediaApproved(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

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
            lambda version: PortfolioMediaRejected(
                image_id=self.id,
                vendor_id=self.vendor_id,
                reason=clean_reason,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
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
        self._assign(
            candidate,
            lambda version: PortfolioMediaDeactivated(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def reorder(self, new_order: int) -> None:
        self._ensure_mutable()
        candidate = replace(self, order=new_order, updated_at=utc_now())
        self._assign(
            candidate,
            lambda version: PortfolioMediaReordered(
                image_id=self.id,
                vendor_id=self.vendor_id,
                order=candidate.order,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
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
        self._assign(
            candidate,
            lambda version: PortfolioCaptionUpdated(
                image_id=self.id,
                vendor_id=self.vendor_id,
                occurred_at=candidate.updated_at,
                aggregate_id=self.id,
                aggregate_version=version,
            ),
        )

    def _assign(self, candidate: "PortfolioImage", event_factory: Callable[[int], object] | None = None) -> None:
        self._commit_candidate(candidate, event_factory)

    def _ensure_mutable(self) -> None:
        if self.is_deleted:
            raise InvalidPortfolioTransition("Deleted portfolio media cannot be changed.")
