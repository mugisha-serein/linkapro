from __future__ import annotations

from threading import Lock, RLock
from typing import Callable
import uuid

from domain.vendors.entities import PortfolioImage

from .errors import VendorApplicationConfigurationError
from .ports import VendorAggregateUnitOfWork


class RepositoryPortfolioImageCreationPort:
    """Compatibility implementation until the database-backed adapter owns this transaction."""

    _locks_guard = Lock()
    _vendor_locks: dict[uuid.UUID, RLock] = {}

    def __init__(self, *, order_allocator, aggregate_uow: VendorAggregateUnitOfWork | None):
        self.order_allocator = order_allocator
        self.aggregate_uow = aggregate_uow

    @classmethod
    def _lock_for(cls, vendor_id: uuid.UUID) -> RLock:
        with cls._locks_guard:
            return cls._vendor_locks.setdefault(vendor_id, RLock())

    def create_at_next_order(
        self,
        *,
        vendor_id: uuid.UUID,
        image_factory: Callable[[int], PortfolioImage],
    ) -> PortfolioImage:
        if self.aggregate_uow is None:
            raise VendorApplicationConfigurationError(
                field_errors={"aggregate_uow": ["Vendor aggregate unit of work is required."]}
            )
        allocate_next_order = getattr(self.order_allocator, "allocate_next_order", None)
        if not callable(allocate_next_order):
            raise VendorApplicationConfigurationError(
                field_errors={"order": ["Portfolio order allocation is not configured."]}
            )

        with self._lock_for(vendor_id):
            next_order = allocate_next_order(vendor_id)
            image = image_factory(next_order)
            return self.aggregate_uow.add_with_pending_events(image)
