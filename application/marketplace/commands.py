from dataclasses import dataclass
import uuid
from typing import Optional

@dataclass(frozen=True)
class UpdateVendorListingCommand:
    vendor_id: uuid.UUID
    business_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    service_area: Optional[str] = None
    cover_image_url: Optional[str] = None

@dataclass(frozen=True)
class PostReviewCommand:
    vendor_id: uuid.UUID
    author_user_id: uuid.UUID
    rating: int
    comment: Optional[str] = None