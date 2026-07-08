from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence
import uuid

from domain.vendors.entities import PortfolioImage
from domain.vendors.interfaces import Page, PageRequest

from .dtos import PageDTO, ServicePackageDTO


@dataclass(frozen=True)
class IdempotencyRecord:
    payload_fingerprint: str
    result: Any


class VendorIdempotencyPort(Protocol):
    def get(self, key: str) -> IdempotencyRecord | None: ...

    def store(self, key: str, *, payload_fingerprint: str, result: Any) -> None: ...


class VendorReadPort(Protocol):
    def list_service_packages(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[ServicePackageDTO]: ...

    def dashboard_summary(self, vendor_id: uuid.UUID) -> dict: ...

    def analytics(self, vendor_id: uuid.UUID) -> dict: ...

    def recent_activity(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[dict]: ...


class PortfolioReorderUnitOfWork(Protocol):
    def list_vendor_images(self, vendor_id: uuid.UUID, page: PageRequest) -> Page[PortfolioImage]: ...

    def persist_reorder(
        self,
        vendor_id: uuid.UUID,
        images: Sequence[PortfolioImage],
        *,
        expected_versions: dict[uuid.UUID, int],
    ) -> Sequence[PortfolioImage]: ...
