from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

from application.vendors.shared.commands import (
    AuthenticatedActor,
    ModeratorActor,
    OMITTED,
    OmittedValue,
    _coerce_actor,
    _coerce_expected_version,
    _coerce_moderator,
    _coerce_required_idempotency_key,
    _coerce_uuid,
)

@dataclass(frozen=True)
class CreateVendorProfileCommand:
    actor: AuthenticatedActor
    business_name: str
    category: str
    description: str
    service_area: str
    contact_email: str
    contact_phone: str
    idempotency_key: str
    custom_category: Optional[str] = None
    website: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "idempotency_key", _coerce_required_idempotency_key(self.idempotency_key))

@dataclass(frozen=True)
class UpdateVendorProfileCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    expected_version: int
    business_name: OmittedValue[str] = OMITTED
    category: OmittedValue[str] = OMITTED
    description: OmittedValue[str] = OMITTED
    service_area: OmittedValue[str] = OMITTED
    contact_email: OmittedValue[str] = OMITTED
    contact_phone: OmittedValue[str] = OMITTED
    custom_category: OmittedValue[str | None] = OMITTED
    website: OmittedValue[str | None] = OMITTED

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class SubmitVendorForReviewCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ApproveVendorCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class RejectVendorCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    expected_version: int
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class SuspendVendorCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    expected_version: int
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ReinstateVendorCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class UpdateVendorBrandingMediaCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    expected_version: int
    profile_image_url: str | None
    profile_image_public_id: str | None
    cover_image_url: str | None
    cover_image_public_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
