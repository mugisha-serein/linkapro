from dataclasses import dataclass
import uuid
from typing import Optional


@dataclass(frozen=True)
class ApproveVendorCommand:
    admin_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class RejectVendorCommand:
    admin_id: uuid.UUID
    vendor_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class SuspendVendorCommand:
    admin_id: uuid.UUID
    vendor_id: uuid.UUID


@dataclass(frozen=True)
class BanUserCommand:
    admin_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class SuspendUserCommand:
    admin_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class ReinstateUserCommand:
    admin_id: uuid.UUID
    user_id: uuid.UUID


@dataclass(frozen=True)
class FlagContentCommand:
    reported_by: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class ResolveFlagCommand:
    admin_id: uuid.UUID
    flag_id: uuid.UUID
    notes: Optional[str] = None
    dismiss: bool = False


@dataclass(frozen=True)
class GenerateMetricsCommand:
    pass