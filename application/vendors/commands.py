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
MAX_IDEMPOTENCY_KEY_LENGTH = 200


def _coerce_uuid(value, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a valid UUID."]}) from exc


def _coerce_expected_version(value, field_name: str = "expected_version") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a nonnegative integer."]})
    return value


def _coerce_optional_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    return _coerce_required_idempotency_key(value)


def _coerce_required_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidVendorCommand(field_errors={"idempotency_key": ["Must be a nonblank string."]})
    key = value.strip()
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidVendorCommand(field_errors={"idempotency_key": ["Must be 200 characters or fewer."]})
    return key


def _coerce_price(value) -> Decimal:
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise InvalidVendorCommand(field_errors={"price": ["Must be a valid decimal."]}) from exc


@dataclass(frozen=True)
class AuthenticatedActor:
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _coerce_uuid(self.user_id, "actor.user_id"))


@dataclass(frozen=True)
class ModeratorActor:
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _coerce_uuid(self.user_id, "moderator.user_id"))


def _coerce_actor(value: AuthenticatedActor) -> AuthenticatedActor:
    if not isinstance(value, AuthenticatedActor):
        raise InvalidVendorCommand(field_errors={"actor": ["Authenticated actor is required."]})
    return value


def _coerce_moderator(value: ModeratorActor) -> ModeratorActor:
    if not isinstance(value, ModeratorActor):
        raise InvalidVendorCommand(field_errors={"moderator": ["Moderator actor is required."]})
    return value


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
    if any(not isinstance(version, ResourceVersion) for version in versions):
        raise InvalidVendorCommand(
            field_errors={"expected_versions": ["Every item must be a ResourceVersion."]}
        )
    resource_ids = tuple(version.resource_id for version in versions)
    if len(resource_ids) != len(set(resource_ids)):
        raise InvalidVendorCommand(
            field_errors={"expected_versions": ["Duplicate resource IDs are not allowed."]}
        )
    return versions


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
    business_name: object = OMITTED
    category: object = OMITTED
    description: object = OMITTED
    service_area: object = OMITTED
    contact_email: object = OMITTED
    contact_phone: object = OMITTED
    custom_category: object = OMITTED
    website: object = OMITTED

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
class AddPortfolioImageCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    public_id: str
    secure_url: str
    idempotency_key: str
    caption: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
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


@dataclass(frozen=True)
class SendInquiryCommand:
    vendor_id: uuid.UUID
    requester_id: uuid.UUID
    client_name: str
    client_email: str
    message: str
    idempotency_key: str
    client_phone: Optional[str] = None
    event_date: Optional[date] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "requester_id", _coerce_uuid(self.requester_id, "requester_id"))
        if self.event_date is not None and (isinstance(self.event_date, datetime) or type(self.event_date) is not date):
            raise InvalidVendorCommand(field_errors={"event_date": ["Must be a date or null."]})
        object.__setattr__(self, "idempotency_key", _coerce_required_idempotency_key(self.idempotency_key))


@dataclass(frozen=True)
class MarkInquiryReadCommand:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    inquiry_id: uuid.UUID
    expected_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        object.__setattr__(self, "inquiry_id", _coerce_uuid(self.inquiry_id, "inquiry_id"))
        object.__setattr__(self, "expected_version", _coerce_expected_version(self.expected_version))
