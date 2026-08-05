from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
import uuid

@dataclass(frozen=True)
class InquiryDTO:
    """Inquiry data returned to vendors.

    ``client_name`` and ``client_email`` are contact snapshots, not
    authorization identity fields.
    """

    id: uuid.UUID
    vendor_id: uuid.UUID
    client_name: str
    client_email: str
    client_phone: Optional[str]
    message: str
    event_date: Optional[date]
    is_read: bool
    created_at: datetime
    version: int
