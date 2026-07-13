from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.vendors.profile.entity import VendorProfile, VendorStatus
from domain.vendors.shared.pagination import Page, PageRequest

class IVendorProfileRepository(ABC):
    @abstractmethod
    def add(self, profile: VendorProfile) -> VendorProfile: ...
    @abstractmethod
    def get_by_id(self, vendor_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def get_by_user_id(self, user_id: uuid.UUID) -> Optional[VendorProfile]: ...
    @abstractmethod
    def list_by_status(self, status: VendorStatus, page: PageRequest | None = None) -> Page[VendorProfile]: ...
    @abstractmethod
    def save(self, profile: VendorProfile, *, expected_version: int) -> VendorProfile: ...
    @abstractmethod
    def delete(self, vendor_id: uuid.UUID) -> None: ...
