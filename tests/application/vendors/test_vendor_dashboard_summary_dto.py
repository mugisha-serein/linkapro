from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import inspect
from typing import get_type_hints
import uuid

import pytest

from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.analytics.dtos import VendorDashboardSummaryDTO
from application.vendors.shared.query_handlers import VendorQueryHandlers
from application.vendors.analytics.ports import VendorReadPort
from application.vendors.analytics.queries import GetVendorDashboardSummaryQuery


class StrictUnusedRepository:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected repository access: {name}")


class AuthorizationPort:
    def __init__(self):
        self.calls = []

    def assert_actor_can_access_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))


class DashboardReadPort:
    def __init__(self, summary):
        self.summary = summary
        self.calls = []

    def dashboard_summary(self, vendor_id):
        self.calls.append(vendor_id)
        return self.summary

    def list_service_packages(self, vendor_id, page):
        raise AssertionError("Service packages must not be queried.")

    def analytics(self, vendor_id):
        raise AssertionError("Analytics must not be queried.")

    def recent_activity(self, vendor_id, page):
        raise AssertionError("Recent activity must not be queried.")


def _summary() -> VendorDashboardSummaryDTO:
    return VendorDashboardSummaryDTO(
        profile_completion=86,
        total_inquiries=12,
        inquiries_mtd=3,
        unread_inquiries=2,
        read_inquiries=10,
        response_rate=83,
        total_packages=4,
        active_packages=2,
        approved_packages=2,
        pending_packages=1,
        rejected_packages=1,
        portfolio_count=7,
        account_status="approved",
        service_area="Kigali",
    )


def test_vendor_dashboard_summary_dto_is_immutable_and_has_the_complete_contract():
    summary = _summary()

    assert tuple(field.name for field in fields(VendorDashboardSummaryDTO)) == (
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
    )

    with pytest.raises(FrozenInstanceError):
        summary.total_inquiries = 99


def test_vendor_read_port_dashboard_summary_returns_typed_dto():
    signature = inspect.signature(VendorReadPort.dashboard_summary)
    hints = get_type_hints(VendorReadPort.dashboard_summary)

    assert tuple(signature.parameters) == ("self", "vendor_id")
    assert hints["vendor_id"] is uuid.UUID
    assert hints["return"] is VendorDashboardSummaryDTO


def test_vendor_query_handler_authorizes_and_returns_dashboard_summary_dto_unchanged():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    summary = _summary()
    read_port = DashboardReadPort(summary)
    authorization = AuthorizationPort()
    unused = StrictUnusedRepository()
    handler = VendorQueryHandlers(
        vendor_repo=unused,
        image_repo=unused,
        inquiry_repo=unused,
        read_repo=read_port,
        authorization_port=authorization,
    )

    result = handler.get_dashboard_summary(
        GetVendorDashboardSummaryQuery(actor=actor, vendor_id=vendor_id)
    )

    assert result is summary
    assert isinstance(result, VendorDashboardSummaryDTO)
    assert authorization.calls == [(actor, vendor_id)]
    assert read_port.calls == [vendor_id]


def test_vendor_query_handler_dashboard_summary_return_annotation_is_typed():
    hints = get_type_hints(VendorQueryHandlers.get_dashboard_summary)

    assert hints["return"] is VendorDashboardSummaryDTO
