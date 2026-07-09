from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import inspect
from typing import get_type_hints
import uuid

import pytest

from application.vendors.commands import AuthenticatedActor
from application.vendors.dtos import VendorAnalyticsDTO
from application.vendors.handlers import VendorQueryHandlers
from application.vendors.ports import VendorReadPort
from application.vendors.queries import GetVendorAnalyticsQuery


class StrictUnusedRepository:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected repository access: {name}")


class AuthorizationPort:
    def __init__(self):
        self.calls = []

    def assert_actor_can_access_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))


class AnalyticsReadPort:
    def __init__(self, analytics):
        self.analytics_result = analytics
        self.calls = []

    def analytics(self, vendor_id):
        self.calls.append(vendor_id)
        return self.analytics_result

    def dashboard_summary(self, vendor_id):
        raise AssertionError("Dashboard summary must not be queried.")

    def list_service_packages(self, vendor_id, page):
        raise AssertionError("Service packages must not be queried.")

    def recent_activity(self, vendor_id, page):
        raise AssertionError("Recent activity must not be queried.")


def _analytics(
    *,
    avg_response_time_hours: float | None = None,
    conversion_rate: float | None = None,
) -> VendorAnalyticsDTO:
    return VendorAnalyticsDTO(
        profile_completion=86,
        total_inquiries=12,
        inquiries_mtd=3,
        unread_inquiries=2,
        read_inquiries=10,
        response_rate=83.33,
        total_packages=4,
        active_packages=2,
        approved_packages=2,
        pending_packages=1,
        rejected_packages=1,
        portfolio_count=7,
        account_status="approved",
        service_area="Kigali",
        avg_response_time_hours=avg_response_time_hours,
        conversion_rate=conversion_rate,
        unavailable_metrics=("avg_response_time_hours", "conversion_rate"),
    )


def test_vendor_analytics_dto_is_immutable_and_has_explicit_typed_fields():
    analytics = _analytics()
    hints = get_type_hints(VendorAnalyticsDTO)

    assert tuple(field.name for field in fields(VendorAnalyticsDTO)) == (
        "profile_completion",
        "total_inquiries",
        "inquiries_mtd",
        "unread_inquiries",
        "read_inquiries",
        "response_rate",
        "total_packages",
        "active_packages",
        "approved_packages",
        "pending_packages",
        "rejected_packages",
        "portfolio_count",
        "account_status",
        "service_area",
        "avg_response_time_hours",
        "conversion_rate",
        "unavailable_metrics",
    )
    assert hints == {
        "profile_completion": int,
        "total_inquiries": int,
        "inquiries_mtd": int,
        "unread_inquiries": int,
        "read_inquiries": int,
        "response_rate": float,
        "total_packages": int,
        "active_packages": int,
        "approved_packages": int,
        "pending_packages": int,
        "rejected_packages": int,
        "portfolio_count": int,
        "account_status": str,
        "service_area": str,
        "avg_response_time_hours": float | None,
        "conversion_rate": float | None,
        "unavailable_metrics": tuple[str, ...],
    }

    with pytest.raises(FrozenInstanceError):
        analytics.total_inquiries = 99


def test_vendor_analytics_dto_accepts_null_and_available_metric_values():
    unavailable = _analytics()
    available = _analytics(avg_response_time_hours=2.5, conversion_rate=14.75)

    assert unavailable.avg_response_time_hours is None
    assert unavailable.conversion_rate is None
    assert available.avg_response_time_hours == 2.5
    assert available.conversion_rate == 14.75


def test_vendor_read_port_analytics_returns_typed_dto():
    signature = inspect.signature(VendorReadPort.analytics)
    hints = get_type_hints(VendorReadPort.analytics)

    assert tuple(signature.parameters) == ("self", "vendor_id")
    assert hints["vendor_id"] is uuid.UUID
    assert hints["return"] is VendorAnalyticsDTO


def test_vendor_query_handler_authorizes_and_returns_analytics_dto_unchanged():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    analytics = _analytics()
    read_port = AnalyticsReadPort(analytics)
    authorization = AuthorizationPort()
    unused = StrictUnusedRepository()
    handler = VendorQueryHandlers(
        vendor_repo=unused,
        image_repo=unused,
        inquiry_repo=unused,
        read_repo=read_port,
        authorization_port=authorization,
    )

    result = handler.get_analytics(
        GetVendorAnalyticsQuery(actor=actor, vendor_id=vendor_id)
    )

    assert result is analytics
    assert isinstance(result, VendorAnalyticsDTO)
    assert authorization.calls == [(actor, vendor_id)]
    assert read_port.calls == [vendor_id]


def test_vendor_query_handler_analytics_return_annotation_is_typed():
    hints = get_type_hints(VendorQueryHandlers.get_analytics)

    assert hints["return"] is VendorAnalyticsDTO
