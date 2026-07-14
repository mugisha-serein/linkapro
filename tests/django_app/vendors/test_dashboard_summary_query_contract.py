from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.analytics.dtos import (
    VendorDashboardSummaryDTO,
    VendorPortfolioQualityTrendDTO,
    VendorViewsTrendPointDTO,
)
from application.vendors.analytics.queries import (
    GetVendorDashboardSummaryQuery,
    GetVendorPortfolioQualityTrendQuery,
    GetVendorViewsTrendQuery,
)
from django_app.vendors.views.analytics import (
    VendorDashboardSummaryView,
    VendorPortfolioQualityTrendView,
    VendorSecurityActionsView,
    VendorViewsTrendView,
)


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


def test_views_trend_view_builds_actor_aware_query():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id), query_params={"months": "3"})
    profile = SimpleNamespace(id=vendor_id)
    handlers = Mock()
    handlers.get_views_trend.return_value = (
        VendorViewsTrendPointDTO(month="2026-05", views=1),
        VendorViewsTrendPointDTO(month="2026-06", views=2),
        VendorViewsTrendPointDTO(month="2026-07", views=3),
    )

    with patch(
        "django_app.vendors.views.analytics._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.analytics.get_query_handlers",
        return_value=handlers,
    ):
        response = VendorViewsTrendView().get(request)

    query = handlers.get_views_trend.call_args.args[0]
    assert isinstance(query, GetVendorViewsTrendQuery)
    assert query.actor.user_id == user_id
    assert query.vendor_id == vendor_id
    assert query.months == 3
    assert response.status_code == 200
    assert response.data == [
        {"month": "2026-05", "views": 1},
        {"month": "2026-06", "views": 2},
        {"month": "2026-07", "views": 3},
    ]


def test_portfolio_quality_trend_view_builds_actor_aware_query():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id), query_params={})
    profile = SimpleNamespace(id=vendor_id)
    handlers = Mock()
    handlers.get_portfolio_quality_trend.return_value = VendorPortfolioQualityTrendDTO(
        current_average_score=90.0,
        scored_images=2,
        points=(),
        unavailable_metrics=("portfolio_quality_snapshots",),
        schema_gap="A real quality trend requires periodic snapshots.",
        proposed_schema={"model": "PortfolioQualitySnapshot"},
    )

    with patch(
        "django_app.vendors.views.analytics._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.analytics.get_query_handlers",
        return_value=handlers,
    ):
        response = VendorPortfolioQualityTrendView().get(request)

    query = handlers.get_portfolio_quality_trend.call_args.args[0]
    assert isinstance(query, GetVendorPortfolioQualityTrendQuery)
    assert query.actor.user_id == user_id
    assert query.vendor_id == vendor_id
    assert response.status_code == 200
    assert response.data["current_average_score"] == 90.0
    assert response.data["points"] == ()
    assert response.data["unavailable_metrics"] == ("portfolio_quality_snapshots",)
    assert response.data["proposed_schema"] == {"model": "PortfolioQualitySnapshot"}


def test_security_actions_view_loads_recent_audit_actions_for_vendor():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id), query_params={"limit": "2"})
    profile = SimpleNamespace(id=vendor_id)
    actions = [
        {
            "id": str(uuid.uuid4()),
            "admin": None,
            "action_type": "suspend_vendor",
            "target_type": "vendor_profile",
            "target_id": str(vendor_id),
            "details": {"reason": "policy"},
            "created_at": "2026-07-14T10:00:00+00:00",
        },
    ]

    with patch(
        "django_app.vendors.views.analytics._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.analytics.recent_security_actions",
        return_value=actions,
    ) as recent_actions:
        response = VendorSecurityActionsView().get(request)

    recent_actions.assert_called_once_with(vendor_id, limit=2)
    assert response.status_code == 200
    assert response.data == actions


def test_security_actions_view_rejects_invalid_limit():
    request = SimpleNamespace(user=SimpleNamespace(id=uuid.uuid4()), query_params={"limit": "0"})
    profile = SimpleNamespace(id=uuid.uuid4())

    with patch(
        "django_app.vendors.views.analytics._get_current_vendor_profile",
        return_value=(profile, None),
    ):
        response = VendorSecurityActionsView().get(request)

    assert response.status_code == 400
    assert response.data["code"] == "vendor_security_actions_limit_invalid"
