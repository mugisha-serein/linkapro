from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import re
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
    starting_price: Optional[Decimal] = None
    min_package_price: Optional[Decimal] = None
    max_package_price: Optional[Decimal] = None
    currency: Optional[str] = None

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
    author_display_name: str = "Verified customer"
    rating: int
    comment: Optional[str]
    created_at: datetime

    @classmethod
    def from_dto(cls, dto):
        return cls(
            id=str(dto.id),
            vendor_id=str(dto.vendor_id),
            rating=dto.rating,
            comment=dto.comment,
            created_at=dto.created_at,
        )


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
    min_price: Optional[Decimal] = Field(default=None, ge=0)
    max_price: Optional[Decimal] = Field(default=None, ge=0)
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


class InternalListingUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_id: uuid.UUID
    external_id: Optional[str] = Field(default=None, max_length=128)
    business_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    custom_category: Optional[str] = Field(default=None, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    service_area: str = Field(min_length=1, max_length=200)
    tags: Optional[list[str] | str] = None
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    average_rating: float = Field(default=0.0, ge=0, le=5)
    total_reviews: int = Field(default=0, ge=0)
    is_verified: bool = False
    approval_status: str = Field(default="approved", max_length=30)
    status: Optional[str] = Field(default=None, max_length=30)
    is_approved: bool = False
    search_rank_score: float = 0.0
    starting_price: Optional[Decimal] = Field(default=None, ge=0)
    min_package_price: Optional[Decimal] = Field(default=None, ge=0)
    max_package_price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=10)

    @field_validator("category", "approval_status", "status")
    @classmethod
    def _normalize_choices(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Value cannot be blank.")
        return normalized

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            return None
        if not re.fullmatch(r"[A-Z]{3,10}", normalized):
            raise ValueError("currency must use uppercase alphabetic code text.")
        return normalized

    @field_validator("cover_image_url")
    @classmethod
    def _validate_public_image_url(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.startswith("https://"):
            raise ValueError("cover_image_url must be HTTPS.")
        if "/media/" in normalized or "vendor_portfolio_uploads" in normalized:
            raise ValueError("cover_image_url must not reference private media storage.")
        return normalized

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, value):
        if value is None or value == "":
            return value
        if isinstance(value, str):
            return value[:500]
        if isinstance(value, list):
            return [str(item).strip()[:64] for item in value if str(item).strip()][:20]
        raise ValueError("tags must be a string or list of strings.")

    @model_validator(mode="after")
    def _validate_status_consistency(self):
        normalized_status = self.approval_status or self.status or ""
        allowed = {"approved", "pending_review", "draft", "rejected", "suspended"}
        if normalized_status not in allowed:
            raise ValueError("approval_status is invalid.")
        if self.is_approved and normalized_status != "approved":
            raise ValueError("is_approved can be true only when approval_status is approved.")
        if self.min_package_price is not None and self.max_package_price is not None and self.min_package_price > self.max_package_price:
            raise ValueError("min_package_price cannot be greater than max_package_price.")
        if self.starting_price is not None and self.min_package_price is not None and self.starting_price != self.min_package_price:
            raise ValueError("starting_price must match min_package_price.")
        return self
