from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class VendorDashboardSummaryDTO:
    profile_completion: int
    total_inquiries: int
    inquiries_mtd: int
    unread_inquiries: int
    read_inquiries: int
    response_rate: int
    total_packages: int
    active_packages: int
    approved_packages: int
    pending_packages: int
    rejected_packages: int
    portfolio_count: int
    account_status: str
    service_area: str

@dataclass(frozen=True)
class VendorAnalyticsDTO:
    profile_completion: int
    total_inquiries: int
    inquiries_mtd: int
    unread_inquiries: int
    read_inquiries: int
    response_rate: float
    total_packages: int
    active_packages: int
    approved_packages: int
    pending_packages: int
    rejected_packages: int
    portfolio_count: int
    account_status: str
    service_area: str
    avg_response_time_hours: float | None
    conversion_rate: float | None
    unavailable_metrics: tuple[str, ...]

@dataclass(frozen=True)
class VendorActivityDTO:
    id: str
    type: str
    message: str
    created_at: str
