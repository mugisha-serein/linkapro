from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from datetime import datetime
from typing import Optional, List
import re

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

    @classmethod
    def from_dto(cls, dto):
        return cls(
            items=[VendorListingResponse.from_dto(item) for item in dto.items],
            total=dto.total,
            page=dto.page,
            page_size=dto.page_size,
            total_pages=dto.total_pages,
        )

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


class MarketplaceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: Optional[str] = Field(default=None, max_length=128)
    category: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=128)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=20, ge=1, le=50)

    @field_validator("q", "category", "location")
    @classmethod
    def _validate_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", value.strip())
        if not normalized:
            return None
        if not all(ch.isprintable() for ch in normalized):
            raise ValueError("Search text must contain printable characters only.")
        return normalized

    @model_validator(mode="after")
    def _validate_rating_alias(self):
        if self.min_rating is not None and self.rating is not None and self.min_rating != self.rating:
            raise ValueError("min_rating and rating must match when both are provided.")
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot be greater than max_price.")
        return self
