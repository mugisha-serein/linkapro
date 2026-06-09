from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SearchVendorsQuery:
    query: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    min_rating: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    page: int = 1
    page_size: int = 20

@dataclass(frozen=True)
class GetVendorListingQuery:
    vendor_id: str   # UUID as string

@dataclass(frozen=True)
class GetVendorReviewsQuery:
    vendor_id: str
    page: int = 1
    page_size: int = 10
