from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from application.vendors.commands import AuthenticatedActor
from application.vendors.dtos import VendorDashboardSummaryDTO
from application.vendors.queries import GetVendorDashboardSummaryQuery
from django_app.vendors.views.analytics import VendorDashboardSummaryView


def test_dashboard_summary_view_builds_actor_aware_query():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id))
    profile = SimpleNamespace(id=vendor_id)
    summary = VendorDashboardSummaryDTO(
        profile_completion=100,
        total_inquiries=0,
        inquiries_mtd=0,
        unread_inquiries=0,
        read_inquiries=0,
        response_rate=0,
        total_packages=0,
        active_packages=0,
        approved_packages=0,
        pending_packages=0,
        rejected_packages=0,
        portfolio_count=0,
        account_status="approved",
        service_area="Kigali",
    )
    handlers = Mock()
    handlers.get_dashboard_summary.return_value = summary

    with patch(
        "django_app.vendors.views.analytics._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.analytics.get_query_handlers",
        return_value=handlers,
    ):
        response = VendorDashboardSummaryView().get(request)

    query = handlers.get_dashboard_summary.call_args.args[0]
    assert isinstance(query, GetVendorDashboardSummaryQuery)
    assert isinstance(query.actor, AuthenticatedActor)
    assert query.actor.user_id == user_id
    assert query.vendor_id == vendor_id
    assert response.status_code == 200
    assert response.data["account_status"] == "approved"
