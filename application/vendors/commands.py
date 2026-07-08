from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, Mapping, Optional
import uuid

from .errors import InvalidVendorCommand


class _Omitted:
    def __repr__(self) -> str:
        return "OMITTED"


OMITTED = _Omitted()


def _coerce_uuid(value, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a valid UUID."]}) from exc


def _coerce_optional_uuid(value, field_name: str) -> uuid.UUID | None:
    if value is None:
        return None
    return _coerce_uuid(value, field_name)


def _coerce_expected_version(value, field_name: str = "expected_version") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a nonnegative integer."]})
    return value


def _coerce_optional_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidVendorCommand(field_errors={"idempotency_key": ["Must be a nonblank string."]})
    return value.strip()


def _coerce_price(value) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise InvalidVendorCommand(field_errors={"price": ["Must be a valid decimal."]}) from exc


@dataclass(frozen=True)
class ResourceVersion:
    resource_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", _coerce_uuid(self.resource_id, "resource_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


def _coerce_resource_versions(value: Iterable[ResourceVersion] | Mapping[uuid.UUID, int]) -> tuple[ResourceVersion, ...]:
    if isinstance(value, Mapping):
        versions = tuple(ResourceVersion(resource_id=key, expected_version=version) for key, version in value.items())
    else:
        versions = tuple(value)
    if not versions:
        raise InvalidVendorCommand(field_errors={"expected_versions": ["At least one version is required."]})
    return versions


@dataclass(frozen=True)
class CreateVendorProfileCommand:
    user_id: uuid.UUID
    business_name: str
    category: str
    description: str
    service_area: str
    contact_email: str
    contact_phone: str
    custom_category: Optional[str] = None
    website: Optional[str] = None
    idempotency_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _coerce_uuid(self.user_id, "user_id"))
        object.__setattr__(self, "idempotency_key", _coerce_optional_idempotency_key(self.idempotency_key))


@dataclass(frozen=True)
class UpdateVendorProfileCommand:
    vendor_id: uuid.UUID
    expected_version: int
    business_name: object = OMITTED
    category: object = OMITTED
    description: object = OMITTED
    service_area: object = OMITTED
    contact_email: object = OMITTED
    contact_phone: object = OMITTED
    custom_category: object = OMITTED
    website: object = OMITTED

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class SubmitVendorForReviewCommand:
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class ApproveVendorCommand:
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class RejectVendorCommand:
    vendor_id: uuid.UUID
    expected_version: int
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class SuspendVendorCommand:
    vendor_id: uuid.UUID
    expected_version: int
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class ReinstateVendorCommand:
    vendor_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class AddPortfolioImageCommand:
    vendor_id: uuid.UUID
    public_id: str
    secure_url: str
    caption: Optional[str] = None
    idempotency_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "idempotency_key", _coerce_optional_idempotency_key(self.idempotency_key))


@dataclass(frozen=True)
class DeletePortfolioImageCommand:
    vendor_id: uuid.UUID
    image_id: uuid.UUID
    expected_version: int
    deleted_by_id: Optional[uuid.UUID] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "image_id", _coerce_uuid(self.image_id, "image_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
        object.__setattr__(self, "deleted_by_id", _coerce_optional_uuid(self.deleted_by_id, "deleted_by_id"))


@dataclass(frozen=True)
class ReorderPortfolioImagesCommand:
    vendor_id: uuid.UUID
    image_ids_in_order: tuple[uuid.UUID, ...]
    expected_versions: tuple[ResourceVersion, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(
            self,
            "image_ids_in_order",
            tuple(_coerce_uuid(image_id, "image_ids_in_order") for image_id in self.image_ids_in_order),
        )
        object.__setattr__(self, "expected_versions", _coerce_resource_versions(self.expected_versions))


@dataclass(frozen=True)
class CreateServicePackageCommand:
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str = "RWF"
    package_tier: str = "standard"
    idempotency_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "price", _coerce_price(self.price))
        object.__setattr__(self, "idempotency_key", _coerce_optional_idempotency_key(self.idempotency_key))


@dataclass(frozen=True)
class UpdateServicePackageCommand:
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    package_tier: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
        if self.price is not None:
            object.__setattr__(self, "price", _coerce_price(self.price))


@dataclass(frozen=True)
class DeactivateServicePackageCommand:
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int
    deleted_by_id: Optional[uuid.UUID] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
        object.__setattr__(self, "deleted_by_id", _coerce_optional_uuid(self.deleted_by_id, "deleted_by_id"))


@dataclass(frozen=True)
class ActivateServicePackageCommand:
    vendor_id: uuid.UUID
    package_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "package_id", _coerce_uuid(self.package_id, "package_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))


@dataclass(frozen=True)
class SendInquiryCommand:
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    client_phone: Optional[str] = None
    event_date: Optional[date] = None
    idempotency_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        if isinstance(self.event_date, datetime):
            raise InvalidVendorCommand(field_errors={"event_date": ["Use a date, not a datetime."]})
        object.__setattr__(self, "idempotency_key", _coerce_optional_idempotency_key(self.idempotency_key))


@dataclass(frozen=True)
class MarkInquiryReadCommand:
    vendor_id: uuid.UUID
    inquiry_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "inquiry_id", _coerce_uuid(self.inquiry_id, "inquiry_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
