import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from domain.shared.utils import utc_now


@dataclass
class VendorListing:
    """Read‑only projection of a vendor for marketplace search."""
    id: uuid.UUID
    vendor_id: uuid.UUID          # reference to VendorProfile
    business_name: str
    category: str
    description: str
    service_area: str
    cover_image_url: Optional[str]
    average_rating: float = 0.0
    total_reviews: int = 0
    is_verified: bool = False
    starting_price: Optional[Decimal] = None
    min_package_price: Optional[Decimal] = None
    max_package_price: Optional[Decimal] = None
    currency: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class Review:
    id: uuid.UUID
    vendor_id: uuid.UUID
    author_user_id: uuid.UUID
    rating: int                    # 1-5
    comment: Optional[str]
    is_verified_purchase: bool = False
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        if not 1 <= self.rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
