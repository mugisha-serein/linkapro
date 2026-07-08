from __future__ import annotations

from typing import Callable, Protocol, Sequence, TypeVar
import uuid

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from domain.vendors.interfaces import Page, PageRequest

from .commands import AuthenticatedActor, ModeratorActor
from .dtos import PageDTO, PortfolioImageDTO, ServicePackageDTO

T = TypeVar("T")
VendorAggregateT = TypeVar("VendorAggregateT", VendorProfile, PortfolioImage, ServicePackage, Inquiry)


class VendorIdempotencyPort(Protocol):
    def execute_once(
        self,
        *,
        scope: str,
        actor_id: uuid.UUID,
        key: str,
        payload_fingerprint: str,
        operation: Callable[[], T],
    ) -> T: ...


class VendorAuthorizationPort(Protocol):
    def assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_actor_can_access_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None: ...


class VendorReadPort(Protocol):
    def list_service_packages(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[ServicePackageDTO]: ...

    def dashboard_summary(self, vendor_id: uuid.UUID) -> dict: ...

    def analytics(self, vendor_id: uuid.UUID) -> dict: ...

    def recent_activity(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[dict]: ...


class VendorAggregateUnitOfWork(Protocol):
    """Atomically persists one vendor aggregate with its pending domain events."""

    def add_with_pending_events(self, aggregate: VendorAggregateT) -> VendorAggregateT: ...

    def save_with_pending_events(
        self,
        aggregate: VendorAggregateT,
        *,
        expected_version: int,
    ) -> VendorAggregateT: ...


class PortfolioReorderUnitOfWork(Protocol):
    """Atomically persists reordered portfolio images with their pending domain events."""

    def list_vendor_images(self, vendor_id: uuid.UUID, page: PageRequest) -> Page[PortfolioImage]: ...

    def persist_reorder(
        self,
        vendor_id: uuid.UUID,
        images: Sequence[PortfolioImage],
        *,
        expected_versions: dict[uuid.UUID, int],
    ) -> Sequence[PortfolioImage]: ...


class PortfolioOrderAllocator(Protocol):
    def allocate_next_order(self, vendor_id: uuid.UUID) -> int: ...
