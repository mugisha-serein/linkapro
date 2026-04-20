from dataclasses import dataclass
import uuid
from datetime import datetime

@dataclass(frozen=True)
class VendorSubmittedForReview:
    vendor_id: uuid.UUID
    user_id: uuid.UUID
    occurred_at: datetime

@dataclass(frozen=True)
class VendorApproved:
    vendor_id: uuid.UUID
    occurred_at: datetime

@dataclass(frozen=True)
class VendorRejected:
    vendor_id: uuid.UUID
    reason: str
    occurred_at: datetime

@dataclass(frozen=True)
class VendorSuspended:
    vendor_id: uuid.UUID
    occurred_at: datetime

@dataclass(frozen=True)
class InquiryReceived:
    inquiry_id: uuid.UUID
    vendor_id: uuid.UUID
    occurred_at: datetime