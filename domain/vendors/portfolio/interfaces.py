from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.vendors.portfolio.entity import PortfolioImage
from domain.vendors.shared.pagination import Page, PageRequest

class IPortfolioImageRepository(ABC):
    @abstractmethod
    def add(self, image: PortfolioImage) -> PortfolioImage: ...

    @abstractmethod
    def get_by_id(self, image_id: uuid.UUID) -> Optional[PortfolioImage]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, image_id: uuid.UUID) -> Optional[PortfolioImage]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[PortfolioImage]: ...
    @abstractmethod
    def save(self, image: PortfolioImage, *, expected_version: int) -> PortfolioImage: ...
    @abstractmethod
    def delete(self, image_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None: ...

    @abstractmethod
    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        image_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> None: ...
