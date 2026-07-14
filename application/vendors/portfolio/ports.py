from __future__ import annotations

from typing import Callable, Protocol, Sequence
import uuid

from domain.vendors.portfolio.entity import PortfolioImage

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
