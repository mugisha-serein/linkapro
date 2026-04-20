from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import uuid

class VendorListingResponse(BaseModel):
    id: str
    business_name: str
    category: str
    description: str
    service_area: str
    cover_image_url: Optional[str]
    average_rating: float
    total_reviews: int
    is_verified: bool

    @classmethod
    def from_dto(cls, dto):
        return cls(**dto.__dict__)

class SearchResponse(BaseModel):
    items: List[VendorListingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class ReviewResponse(BaseModel):
    id: str
    vendor_id: str
    author_user_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime

    @classmethod
    def from_dto(cls, dto):
        return cls(**dto.__dict__)

class PostReviewRequest(BaseModel):
    author_user_id: str  # UUID as string
    rating: int
    comment: Optional[str] = None