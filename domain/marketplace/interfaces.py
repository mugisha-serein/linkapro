from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import uuid

from .entities import VendorListing, Review


class IVendorListingRepository(ABC):
    @abstractmethod
    async def get_by_vendor_id(self, vendor_id: uuid.UUID) -> Optional[VendorListing]: ...
    
    @abstractmethod
    async def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        location: Optional[str] = None,
        min_rating: Optional[float] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[VendorListing], int]: ...   # returns (items, total_count)
    
    @abstractmethod
    async def save(self, listing: VendorListing) -> VendorListing: ...
    
    @abstractmethod
    async def delete(self, vendor_id: uuid.UUID) -> None: ...


class IReviewRepository(ABC):
    @abstractmethod
    async def get_by_id(self, review_id: uuid.UUID) -> Optional[Review]: ...
    
    @abstractmethod
    async def list_by_vendor(self, vendor_id: uuid.UUID, limit: int = 20, offset: int = 0) -> List[Review]: ...
    
    @abstractmethod
    async def save(self, review: Review) -> Review: ...
    
    @abstractmethod
    async def delete(self, review_id: uuid.UUID) -> None: ...
    
    @abstractmethod
    async def get_average_rating(self, vendor_id: uuid.UUID) -> float: ...
