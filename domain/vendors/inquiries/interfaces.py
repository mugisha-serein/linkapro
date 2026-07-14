from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional
import uuid

from domain.vendors.inquiries.entity import Inquiry
from domain.vendors.shared.pagination import Page, PageRequest

InquiryDateRange = tuple[date | datetime | None, date | datetime | None]


class IInquiryRepository(ABC):
    @abstractmethod
    def add(self, inquiry: Inquiry) -> Inquiry: ...

    @abstractmethod
    def get_by_id(self, inquiry_id: uuid.UUID) -> Optional[Inquiry]: ...

    @abstractmethod
    def get_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> Optional[Inquiry]: ...

    @abstractmethod
    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[Inquiry]: ...

    @abstractmethod
    def search(
        self,
        vendor_id: uuid.UUID,
        query: str | None,
        status_filter: str | None,
        date_range: InquiryDateRange | None,
        page: PageRequest | None = None,
    ) -> Page[Inquiry]: ...

    @abstractmethod
    def save(self, inquiry: Inquiry, *, expected_version: int) -> Inquiry: ...
    @abstractmethod
    def delete(self, inquiry_id: uuid.UUID) -> None: ...

    @abstractmethod
    def delete_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> None: ...
