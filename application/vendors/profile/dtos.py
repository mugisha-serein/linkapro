from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

@dataclass(frozen=True)
class VendorProfileDTO:
    id: uuid.UUID
    user_id: uuid.UUID
    business_name: str
    category: str
    description: str
    service_area: str
    contact_email: str
    contact_phone: str
    custom_category: Optional[str]
    website: Optional[str]
    profile_image_url: Optional[str]
    cover_image_url: Optional[str]
    status: str
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    rejection_reason: Optional[str]
    version: int
