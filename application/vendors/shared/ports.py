from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Generic, Literal, Protocol, TypeAlias, TypeVar
import uuid

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from application.vendors.shared.commands import AuthenticatedActor, ModeratorActor

T = TypeVar("T")
VendorAggregateT = TypeVar("VendorAggregateT", VendorProfile, PortfolioImage, ServicePackage, Inquiry)
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

class VendorAuthorizationPort(Protocol):
    def assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_actor_can_access_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None: ...

    def assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None: ...

class VendorAggregateUnitOfWork(Protocol):
    """Atomically persists one vendor aggregate with its pending domain events."""

    def add_with_pending_events(self, aggregate: VendorAggregateT) -> VendorAggregateT: ...

    def save_with_pending_events(
        self,
        aggregate: VendorAggregateT,
        *,
        expected_version: int,
    ) -> VendorAggregateT: ...

VendorIdempotencyOutcome: TypeAlias = (
    VendorIdempotencyCompleted[T]
    | VendorIdempotencyInProgress
    | VendorIdempotencyRetryableFailed
    | VendorIdempotencyExpired
)
