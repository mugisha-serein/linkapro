from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

from application.vendors.shared.commands import (
    AuthenticatedActor,
    ModeratorActor,
    ResourceVersion,
    _coerce_actor,
    _coerce_expected_version,
    _coerce_moderator,
    _coerce_required_idempotency_key,
    _coerce_resource_versions,
    _coerce_uuid,
)

@dataclass(frozen=True)
class AddPortfolioImageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    public_id: str
    secure_url: str
    idempotency_key: str
    image_id: uuid.UUID | None = None
    caption: Optional[str] = None
    media_type: str = "image"
    upload_status: str = "staged"
    quality_status: str = "pending_analysis"
    visibility_status: str = "private"
    original_filename: Optional[str] = None
    mime_type: str = ""
    file_size: int = 0
    cloudinary_public_id: Optional[str] = None
    cloudinary_secure_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        if self.image_id is not None:
            object.__setattr__(self, "image_id", _coerce_uuid(self.image_id, "image_id"))
        object.__setattr__(self, "idempotency_key", _coerce_required_idempotency_key(self.idempotency_key))

@dataclass(frozen=True)
class DeletePortfolioImageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    image_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "image_id", _coerce_uuid(self.image_id, "image_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ReorderPortfolioImagesCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    image_ids_in_order: tuple[uuid.UUID, ...]
    expected_versions: tuple[ResourceVersion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(
            self,
            "image_ids_in_order",
            tuple(_coerce_uuid(image_id, "image_ids_in_order") for image_id in self.image_ids_in_order),
        )
        object.__setattr__(self, "expected_versions", _coerce_resource_versions(self.expected_versions))

@dataclass(frozen=True)
class QueuePortfolioMediaCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class MarkPortfolioMediaProcessingCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class MarkPortfolioMediaUploadedCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int
    public_id: str
    secure_url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class UpdatePortfolioCaptionCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int
    caption: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ApprovePortfolioMediaCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    media_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "media_id", _coerce_uuid(self.media_id, "media_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
