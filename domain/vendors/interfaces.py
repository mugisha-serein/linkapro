from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar
import uuid

from .entities import VendorProfile, PortfolioImage, ServicePackage, Inquiry, VendorStatus

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    limit: int = 50
    offset: int = 0
    cursor: str | None = None

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 100:
            raise ValueError("Page limit must be between 1 and 100.")
        if self.offset < 0 or self.offset > 10_000:
            raise ValueError("Page offset must be between 0 and 10000.")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None


class IVendorProfileRepository(ABC):
    @abstractmethod
    def get_by_id(self, vendor_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def list_by_status(self, status: VendorStatus, page: PageRequest | None = None) -> Page[VendorProfile]: ...
    @abstractmethod
    def save(self, profile: VendorProfile, expected_version: int | None = None) -> VendorProfile: ...
    @abstractmethod
    def delete(self, vendor_id: uuid.UUID) -> None: ...


class IPortfolioImageRepository(ABC):
    @abstractmethod
    def get_by_id(self, image_id: uuid.UUID) -> Optional[PortfolioImage]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, image_id: uuid.UUID) -> Optional[PortfolioImage]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[PortfolioImage]: ...
    @abstractmethod
    def save(self, image: PortfolioImage, expected_version: int | None = None) -> PortfolioImage: ...
    @abstractmethod
    def delete(self, image_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None: ...

    @abstractmethod
    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        image_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> None: ...


class IServicePackageRepository(ABC):
    @abstractmethod
    def get_by_id(self, package_id: uuid.UUID) -> Optional[ServicePackage]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, package_id: uuid.UUID) -> Optional[ServicePackage]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[ServicePackage]: ...
    @abstractmethod
    def save(self, package: ServicePackage, expected_version: int | None = None) -> ServicePackage: ...
    @abstractmethod
    def delete(self, package_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> Optional[ServicePackage]: ...

    @abstractmethod
    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        package_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[ServicePackage]: ...


class IInquiryRepository(ABC):
    @abstractmethod
    def get_by_id(self, inquiry_id: uuid.UUID) -> Optional[Inquiry]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> Optional[Inquiry]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[Inquiry]: ...
    @abstractmethod
    def save(self, inquiry: Inquiry, expected_version: int | None = None) -> Inquiry: ...
    @abstractmethod
    def delete(self, inquiry_id: uuid.UUID) -> None: ...

    @abstractmethod
    def delete_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> None: ...
