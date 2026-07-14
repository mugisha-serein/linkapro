from __future__ import annotations

from dataclasses import dataclass
import uuid

from domain.vendors.shared.pagination import PageRequest
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.shared.queries import _coerce_actor, _coerce_uuid

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


@dataclass(frozen=True)
class GetVendorViewsTrendQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    months: int = 6

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        if isinstance(self.months, bool):
            raise ValueError("months must be an integer from 1 to 24.")
        months = int(self.months)
        if months < 1 or months > 24:
            raise ValueError("months must be an integer from 1 to 24.")
        object.__setattr__(self, "months", months)


@dataclass(frozen=True)
class GetVendorVisibilityTrendQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID
    months: int = 6

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
        if isinstance(self.months, bool):
            raise ValueError("months must be an integer from 1 to 24.")
        months = int(self.months)
        if months < 1 or months > 24:
            raise ValueError("months must be an integer from 1 to 24.")
        object.__setattr__(self, "months", months)


@dataclass(frozen=True)
class GetVendorPortfolioQualityTrendQuery:
    actor: AuthenticatedActor
    vendor_id: uuid.UUID

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", _coerce_actor(self.actor))
        object.__setattr__(self, "vendor_id", _coerce_uuid(self.vendor_id, "vendor_id"))
