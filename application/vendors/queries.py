from __future__ import annotations

from dataclasses import dataclass
import uuid

from domain.vendors.interfaces import PageRequest

from .commands import AuthenticatedActor
from .errors import InvalidVendorCommand


def _coerce_uuid(value, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise InvalidVendorCommand(field_errors={field_name: ["Must be a valid UUID."]}) from exc


def _coerce_actor(value: AuthenticatedActor) -> AuthenticatedActor:
    if not isinstance(value, AuthenticatedActor):
        raise InvalidVendorCommand(field_errors={"actor": ["Authenticated actor is required."]})
    return value


@dataclass(frozen=True)
class GetVendorQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class ListPortfolioImagesQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    page: PageRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class ListServicePackagesQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    page: PageRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class ListInquiriesQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    page: PageRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class GetVendorDashboardSummaryQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class GetVendorAnalyticsQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))


@dataclass(frozen=True)
class ListRecentVendorActivityQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    page: PageRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
