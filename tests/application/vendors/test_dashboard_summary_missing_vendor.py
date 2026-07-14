from __future__ import annotations

import uuid

import pytest

from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.analytics.dtos import VendorDashboardSummaryDTO
from application.vendors.errors import VendorResourceNotFound
from application.vendors.shared.query_handlers import VendorQueryHandlers
from application.vendors.analytics.queries import GetVendorDashboardSummaryQuery


class VendorRepo:
    def __init__(self, vendor, trace):
        self.vendor = vendor
        self.trace = trace
        self.calls = []

    def get_by_id(self, vendor_id):
        self.trace.append("vendor-load")
        self.calls.append(vendor_id)
        return self.vendor


class AuthorizationPort:
    def __init__(self, trace):
        self.trace = trace
        self.calls = []

    def assert_actor_can_access_vendor(self, actor, vendor_id):
        self.trace.append("authorize")
        self.calls.append((actor, vendor_id))


class DashboardReadPort:
    def __init__(self, summary, trace):
        self.summary = summary
        self.trace = trace
        self.calls = []

    def dashboard_summary(self, vendor_id):
        self.trace.append("dashboard-read")
        self.calls.append(vendor_id)
        return self.summary

    def list_service_packages(self, vendor_id, page):
        raise AssertionError("Package listing must not be used.")

    def analytics(self, vendor_id):
        raise AssertionError("Analytics must not be used.")

    def recent_activity(self, vendor_id, page):
        raise AssertionError("Recent activity must not be used.")


class StrictUnusedRepository:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected repository access: {name}")


def _summary() -> VendorDashboardSummaryDTO:
    return VendorDashboardSummaryDTO(
        profile_completion=80,
        total_inquiries=4,
        inquiries_mtd=1,
        unread_inquiries=1,
        read_inquiries=3,
        response_rate=75,
        total_packages=2,
        active_packages=1,
        approved_packages=1,
        pending_packages=1,
        rejected_packages=0,
        portfolio_count=3,
        account_status="approved",
        service_area="Kigali",
    )


def _handler(*, vendor_repo, read_port, authorization_port):
    unused = StrictUnusedRepository()
    return VendorQueryHandlers(
        vendor_repo=vendor_repo,
        image_repo=unused,
        inquiry_repo=unused,
        read_repo=read_port,
        authorization_port=authorization_port,
    )


def test_dashboard_summary_missing_vendor_raises_before_read_port_call():
    trace = []
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_repo = VendorRepo(None, trace)
    authorization = AuthorizationPort(trace)
    read_port = DashboardReadPort(_summary(), trace)
    handler = _handler(
        vendor_repo=vendor_repo,
        read_port=read_port,
        authorization_port=authorization,
    )

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.get_dashboard_summary(
            GetVendorDashboardSummaryQuery(actor=actor, vendor_id=vendor_id)
        )

    assert exc_info.value.code == "vendor_resource_not_found"
    assert exc_info.value.message == "Vendor not found."
    assert trace == ["authorize", "vendor-load"]
    assert authorization.calls == [(actor, vendor_id)]
    assert vendor_repo.calls == [vendor_id]
    assert read_port.calls == []


def test_dashboard_summary_existing_vendor_calls_read_port_after_existence_check():
    trace = []
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_repo = VendorRepo(object(), trace)
    authorization = AuthorizationPort(trace)
    summary = _summary()
    read_port = DashboardReadPort(summary, trace)
    handler = _handler(
        vendor_repo=vendor_repo,
        read_port=read_port,
        authorization_port=authorization,
    )

    result = handler.get_dashboard_summary(
        GetVendorDashboardSummaryQuery(actor=actor, vendor_id=vendor_id)
    )

    assert result is summary
    assert trace == ["authorize", "vendor-load", "dashboard-read"]
    assert authorization.calls == [(actor, vendor_id)]
    assert vendor_repo.calls == [vendor_id]
    assert read_port.calls == [vendor_id]
