from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Generic, Literal, Protocol, Sequence, TypeAlias, TypeVar
import uuid

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from domain.vendors.events import VendorDomainEvent
from domain.vendors.interfaces import PageRequest

from .commands import AuthenticatedActor, ModeratorActor
from .dtos import PageDTO, PortfolioImageDTO, ServicePackageDTO

T = TypeVar("T")
VendorAggregateT = TypeVar("VendorAggregateT", VendorProfile, PortfolioImage, ServicePackage, Inquiry)
CreatedVendorAggregateT = TypeVar("CreatedVendorAggregateT", VendorProfile, PortfolioImage, ServicePackage, Inquiry)

VENDOR_IDEMPOTENCY_RECORD_EXPIRES_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class VendorIdempotencyCompleted(Generic[T]):
    payload_fingerprint: str
    result: T
    status: Literal["completed"] = "completed"


@dataclass(frozen=True)
class VendorIdempotencyInProgress:
    payload_fingerprint: str
    status: Literal["in_progress"] = "in_progress"


@dataclass(frozen=True)
class VendorIdempotencyRetryableFailed:
    payload_fingerprint: str
    status: Literal["retryable_failed"] = "retryable_failed"


@dataclass(frozen=True)
class VendorIdempotencyExpired:
    payload_fingerprint: str
    status: Literal["expired"] = "expired"


VendorIdempotencyOutcome: TypeAlias = (
    VendorIdempotencyCompleted[T]
    | VendorIdempotencyInProgress
    | VendorIdempotencyRetryableFailed
    | VendorIdempotencyExpired
)


class VendorIdempotencyPort(Protocol):
    def get_outcome(
        self,
        *,
        scope: str,
        actor_id: uuid.UUID,
        key: str,
        payload_fingerprint: str,
        expires_after: timedelta = VENDOR_IDEMPOTENCY_RECORD_EXPIRES_AFTER,
    ) -> VendorIdempotencyOutcome[T] | None: ...

    def execute_once(
        self,
        *,
        scope: str,
        actor_id: uuid.UUID,
        key: str,
        payload_fingerprint: str,
        operation: Callable[[], T],
    ) -> T: ...


class InquiryAbuseProtectionPort(Protocol):
    def assert_inquiry_allowed(
        self,
        *,
        requester_identity: uuid.UUID,
        vendor_id: uuid.UUID,
        payload_digest: str,
    ) -> None: ...


class VendorAuthorizationPort(Protocol):
    def assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_actor_can_access_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None: ...


class VendorReadPort(Protocol):
    def list_service_packages(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[ServicePackageDTO]: ...

    def dashboard_summary(self, vendor_id: uuid.UUID) -> dict: ...

    def analytics(self, vendor_id: uuid.UUID) -> dict: ...

    def recent_activity(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[dict]: ...


class VendorEventDispatcher(Protocol):
    """Persists a vendor domain event for publication."""

    def dispatch(self, event: VendorDomainEvent) -> None: ...


class VendorAggregateUnitOfWork(Protocol):
    """Atomically persists one vendor aggregate with its pending domain events."""

    def add_with_pending_events(self, aggregate: VendorAggregateT) -> VendorAggregateT: ...

    def save_with_pending_events(
        self,
        aggregate: VendorAggregateT,
        *,
        expected_version: int,
    ) -> VendorAggregateT: ...


class VendorCreationUnitOfWork(Protocol):
    """Atomically adds one newly created vendor aggregate with its pending creation events."""

    def add_with_pending_events(self, aggregate: CreatedVendorAggregateT) -> CreatedVendorAggregateT: ...


class PortfolioReorderUnitOfWork(Protocol):
    """Loads and atomically persists the complete active portfolio set for one vendor."""

    def load_active_vendor_images(self, vendor_id: uuid.UUID) -> Sequence[PortfolioImage]: ...

    def persist_reorder(
        self,
        vendor_id: uuid.UUID,
        images: Sequence[PortfolioImage],
        *,
        expected_versions: dict[uuid.UUID, int],
    ) -> Sequence[PortfolioImage]: ...


class PortfolioImageCreationPort(Protocol):
    """Atomically assigns the next vendor order and persists one portfolio image with pending events."""

    def create_at_next_order(
        self,
        *,
        vendor_id: uuid.UUID,
        image_factory: Callable[[int], PortfolioImage],
    ) -> PortfolioImage: ...
