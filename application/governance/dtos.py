from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, Any
import uuid


@dataclass(frozen=True)
class AuditLogDTO:
    id: uuid.UUID
    admin_id: uuid.UUID
    action_type: str
    target_type: str
    target_id: uuid.UUID
    details: Dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ContentFlagDTO:
    id: uuid.UUID
    reported_by: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    reason: str
    status: str
    admin_notes: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class PlatformMetricDTO:
    date: date
    total_users: int
    total_planners: int
    total_vendors: int
    active_vendors: int
    pending_vendor_approvals: int
    total_events: int
    total_inquiries: int
    total_reviews: int
    updated_at: datetime