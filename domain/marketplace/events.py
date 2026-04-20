from dataclasses import dataclass
import uuid
from datetime import datetime

@dataclass(frozen=True)
class VendorListingUpdated:
    vendor_id: uuid.UUID
    occurred_at: datetime

@dataclass(frozen=True)
class ReviewPosted:
    review_id: uuid.UUID
    vendor_id: uuid.UUID
    rating: int
    occurred_at: datetime