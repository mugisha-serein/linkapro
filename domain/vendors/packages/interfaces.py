from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.vendors.packages.entity import ServicePackage
from domain.vendors.shared.pagination import Page, PageRequest


class IServicePackageRepository(ABC):
    @abstractmethod
    def add(self, package: ServicePackage) -> ServicePackage: ...

    @abstractmethod
    def get_by_id(self, package_id: uuid.UUID) -> Optional[ServicePackage]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, package_id: uuid.UUID) -> Optional[ServicePackage]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[ServicePackage]: ...

    @abstractmethod
    def search(
        self,
        vendor_id: uuid.UUID,
        query: str | None,
        tier_filter: str | None,
        page: PageRequest | None = None,
    ) -> Page[ServicePackage]: ...

    @abstractmethod
    def save(self, package: ServicePackage, *, expected_version: int) -> ServicePackage: ...
    @abstractmethod
    def delete(self, package_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> Optional[ServicePackage]: ...

    @abstractmethod
    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        package_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[ServicePackage]: ...
