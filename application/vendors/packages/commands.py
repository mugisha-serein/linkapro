from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import uuid

from application.vendors.errors import InvalidVendorCommand
from application.vendors.shared.commands import (
    AuthenticatedActor,
    ModeratorActor,
    _coerce_actor,
    _coerce_expected_version,
    _coerce_moderator,
    _coerce_required_idempotency_key,
    _coerce_uuid,
)

def _coerce_price(value) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise InvalidVendorCommand(field_errors={"price": ["Must be a valid decimal."]}) from exc

@dataclass(frozen=True)
class CreateServicePackageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    idempotency_key: str
    currency: str = "RWF"
    package_tier: str = "standard"

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "price", _coerce_price(self.price))
        object.__setattr__(self, "idempotency_key", _coerce_required_idempotency_key(self.idempotency_key))

@dataclass(frozen=True)
class UpdateServicePackageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    package_tier: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
        if self.price is not None:
            object.__setattr__(self, "price", _coerce_price(self.price))

@dataclass(frozen=True)
class SubmitServicePackageForApprovalCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ApproveServicePackageCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class RejectServicePackageCommand:
    moderator: ModeratorActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "moderator", _coerce_moderator(self.moderator))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class RestoreServicePackageForReviewCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class DeactivateServicePackageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))

@dataclass(frozen=True)
class ActivateServicePackageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
