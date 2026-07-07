from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Optional, List, TypeVar
import uuid

from .entities import VendorProfile, PortfolioImage, ServicePackage, Inquiry, VendorStatus

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 100:
            raise ValueError("Page limit must be between 1 and 100.")
        if self.offset < 0:
            raise ValueError("Page offset cannot be negative.")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class IVendorProfileRepository(ABC):
    @abstractmethod
    def get_by_id(self, vendor_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def list_by_status(self, status: VendorStatus, page: PageRequest | None = None) -> List[VendorProfile]: ...
    @abstractmethod
    def save(self, profile: VendorProfile, expected_version: object | None = None) -> VendorProfile: ...
    @abstractmethod
    def delete(self, vendor_id: uuid.UUID) -> None: ...


class IPortfolioImageRepository(ABC):
    @abstractmethod
    def get_by_id(self, image_id: uuid.UUID) -> Optional[PortfolioImage]: ...

    def get_for_vendor(self, vendor_id: uuid.UUID, image_id: uuid.UUID) -> Optional[PortfolioImage]:
        image = self.get_by_id(image_id)
        if image and image.vendor_id == vendor_id:
            return image
        return None

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> List[PortfolioImage]: ...
    @abstractmethod
    def save(self, image: PortfolioImage, expected_version: object | None = None) -> PortfolioImage: ...
    @abstractmethod
    def delete(self, image_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None: ...

    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        image_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> None:
        image = self.get_for_vendor(vendor_id, image_id)
        if image:
            self.delete(image_id, deleted_by_id=deleted_by_id)


class IServicePackageRepository(ABC):
    @abstractmethod
    def get_by_id(self, package_id: uuid.UUID) -> Optional[ServicePackage]: ...

    def get_for_vendor(self, vendor_id: uuid.UUID, package_id: uuid.UUID) -> Optional[ServicePackage]:
        package = self.get_by_id(package_id)
        if package and package.vendor_id == vendor_id:
            return package
        return None

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> List[ServicePackage]: ...
    @abstractmethod
    def save(self, package: ServicePackage, expected_version: object | None = None) -> ServicePackage: ...
    @abstractmethod
    def delete(self, package_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> Optional[ServicePackage]: ...

    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        package_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[ServicePackage]:
        package = self.get_for_vendor(vendor_id, package_id)
        if not package:
            return None
        return self.delete(package_id, deleted_by_id=deleted_by_id)


class IInquiryRepository(ABC):
    @abstractmethod
    def get_by_id(self, inquiry_id: uuid.UUID) -> Optional[Inquiry]: ...

    def get_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> Optional[Inquiry]:
        inquiry = self.get_by_id(inquiry_id)
        if inquiry and inquiry.vendor_id == vendor_id:
            return inquiry
        return None

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> List[Inquiry]: ...
    @abstractmethod
    def save(self, inquiry: Inquiry, expected_version: object | None = None) -> Inquiry: ...
    @abstractmethod
    def delete(self, inquiry_id: uuid.UUID) -> None: ...

    def delete_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> None:
        inquiry = self.get_for_vendor(vendor_id, inquiry_id)
        if inquiry:
            self.delete(inquiry_id)
