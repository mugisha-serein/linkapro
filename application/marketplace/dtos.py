from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

@dataclass(frozen=True)
class VendorListingDTO:
    id: str
    business_name: str
    category: str
    description: str
    service_area: str
    cover_image_url: Optional[str]
    average_rating: float
    total_reviews: int
    is_verified: bool

@dataclass(frozen=True)
class ReviewDTO:
    id: str
    vendor_id: str
    author_user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime

@dataclass(frozen=True)
class SearchResultDTO:
    items: list[VendorListingDTO]
    total: int
    page: int
    page_size: int
    total_pages: int