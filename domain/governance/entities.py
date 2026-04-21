"""Governance domain entities."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Date

from domain.shared.utils import utc_now


class AdminActionType(str, Enum):
    APPROVE_VENDOR = "approve_vendor"
    REJECT_VENDOR = "reject_vendor"
    SUSPEND_VENDOR = "suspend_vendor"
    BAN_USER = "ban_user"
    SUSPEND_USER = "suspend_user"
    REINSTATE_USER = "reinstate_user"
    DELETE_CONTENT = "delete_content"
    FLAG_RESOLVE = "flag_resolve"


class FlagStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class ContentType(str, Enum):
    VENDOR_PROFILE = "vendor_profile"
    REVIEW = "review"
    PORTFOLIO_IMAGE = "portfolio_image"


@dataclass
class AuditLog:
    id: uuid.UUID
    admin_id: uuid.UUID
    action_type: AdminActionType
    target_type: str              # e.g., "user", "vendor", "review"
    target_id: uuid.UUID
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ContentFlag:
    id: uuid.UUID
    reported_by: uuid.UUID
    content_type: ContentType
    content_id: uuid.UUID
    reason: str
    status: FlagStatus = FlagStatus.PENDING
    admin_notes: Optional[str] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def mark_reviewed(self, notes: Optional[str] = None) -> None:
        self.status = FlagStatus.REVIEWED
        self.admin_notes = notes
        self.updated_at = utc_now()

    def dismiss(self, notes: Optional[str] = None) -> None:
        self.status = FlagStatus.DISMISSED
        self.admin_notes = notes
        self.updated_at = utc_now()


@dataclass
class PlatformMetric:
    date: Date
    total_users: int = 0
    total_planners: int = 0
    total_vendors: int = 0
    active_vendors: int = 0
    pending_vendor_approvals: int = 0
    total_events: int = 0
    total_inquiries: int = 0
    total_reviews: int = 0
    updated_at: datetime = field(default_factory=utc_now)