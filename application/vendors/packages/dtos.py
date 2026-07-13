from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

@dataclass(frozen=True)
class ServicePackageDTO:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    description: str
    price: Decimal
    currency: str
    package_tier: str
    approval_status: str
    rejection_reason: Optional[str]
    is_active: bool
    is_deleted: bool
    deleted_at: Optional[datetime]
    last_approved_at: Optional[datetime]
    last_vendor_public_edit_at: Optional[datetime]
    next_vendor_edit_allowed_at: Optional[datetime]
    version: int
