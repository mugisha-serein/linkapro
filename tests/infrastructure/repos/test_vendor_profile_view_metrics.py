from datetime import date

import pytest

from django_app.vendors.models import ServicePackage, VendorProfileViewed
from infrastructure.repos.analytics import metrics
from infrastructure.repos.analytics.metrics import (
    active_packages_count,
    log_profile_view,
    profile_strength_score,
    response_rate,
    total_views_trend,
    views_by_month,
    visibility_trend,
)
from infrastructure.repos.analytics.rules import optimization_alerts, profile_strength_suggestions
from tests.factories import create_inquiry, create_service_package, create_vendor_profile

pytestmark = pytest.mark.django_db


def test_profile_view_logging_counts_one_row_per_vendor_and_date():
    vendor = create_vendor_profile(status="approved")

    log_profile_view(vendor.id, viewed_on=date(2026, 7, 14))
    log_profile_view(vendor.id, viewed_on=date(2026, 7, 14))

    row = VendorProfileViewed.objects.get(vendor=vendor, view_date=date(2026, 7, 14))
    assert row.view_count == 2


def test_total_views_trend_returns_zero_filled_monthly_series(monkeypatch):
    vendor = create_vendor_profile(status="approved")
    monkeypatch.setattr(metrics.timezone, "localdate", lambda: date(2026, 7, 14))

    log_profile_view(vendor.id, viewed_on=date(2026, 6, 1))
    log_profile_view(vendor.id, viewed_on=date(2026, 6, 30))
    log_profile_view(vendor.id, viewed_on=date(2026, 7, 14))

    trend = total_views_trend(vendor.id, months=2)

    assert trend == [
        {"month": "2026-06", "views": 2},
        {"month": "2026-07", "views": 1},
    ]
    assert all(set(point) == {"month", "views"} for point in trend)


def test_views_by_month_returns_single_year_monthly_breakdown():
    vendor = create_vendor_profile(status="approved")
    log_profile_view(vendor.id, viewed_on=date(2025, 12, 31))
    log_profile_view(vendor.id, viewed_on=date(2026, 1, 1))
    log_profile_view(vendor.id, viewed_on=date(2026, 2, 14))
    log_profile_view(vendor.id, viewed_on=date(2026, 2, 14))
    log_profile_view(vendor.id, viewed_on=date(2026, 12, 31))
    log_profile_view(vendor.id, viewed_on=date(2027, 1, 1))

    breakdown = views_by_month(vendor.id, 2026)

    assert len(breakdown) == 12
    assert breakdown[0] == {"month": "2026-01", "views": 1}
    assert breakdown[1] == {"month": "2026-02", "views": 2}
    assert breakdown[2] == {"month": "2026-03", "views": 0}
    assert breakdown[-1] == {"month": "2026-12", "views": 1}


def test_visibility_trend_reports_marketplace_impressions_as_unavailable(monkeypatch):
    vendor = create_vendor_profile(status="approved")
    monkeypatch.setattr(metrics.timezone, "localdate", lambda: date(2026, 7, 14))
    log_profile_view(vendor.id, viewed_on=date(2026, 7, 14))

    trend = visibility_trend(vendor.id, months=2)

    assert trend["points"] == [
        {"month": "2026-06", "profile_views": 0, "marketplace_impressions": None},
        {"month": "2026-07", "profile_views": 1, "marketplace_impressions": None},
    ]
    assert trend["unavailable_metrics"] == ("marketplace_search_impressions",)


def test_profile_strength_score_represents_domain_completion_errors():
    complete = create_vendor_profile(
        description="Professional event coverage across Kigali and beyond.",
    )
    incomplete = create_vendor_profile(
        business_name="",
        description="Too short",
        contact_phone="",
    )

    assert profile_strength_score(complete.id) == 100
    assert profile_strength_score(incomplete.id) == 50


def test_profile_strength_score_never_reports_complete_when_domain_errors_remain():
    vendor = create_vendor_profile(
        category="other",
        custom_category="",
        description="Professional event coverage across Kigali and beyond.",
    )

    assert profile_strength_score(vendor.id) == 99


def test_profile_strength_suggestions_map_domain_completion_errors_to_copy():
    vendor = create_vendor_profile(
        business_name="",
        description="Too short",
        contact_phone="",
    )

    assert profile_strength_suggestions(vendor.id) == {
        "business_name": "Add your business name so clients can recognize your brand.",
        "description": "Write a stronger business description with at least 20 characters.",
        "contact_phone": "Add a contact phone number for client inquiries.",
    }


def test_profile_strength_suggestions_include_conditional_domain_errors():
    vendor = create_vendor_profile(
        category="other",
        custom_category="",
        description="Professional event coverage across Kigali and beyond.",
    )

    assert profile_strength_suggestions(vendor.id) == {
        "custom_category": "Describe your service when choosing Other as your category.",
    }


def test_active_packages_count_uses_existing_package_metric_rules():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    create_service_package(
        vendor=vendor,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )
    create_service_package(
        vendor=vendor,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=False,
    )
    create_service_package(
        vendor=vendor,
        approval_status=ServicePackage.ApprovalStatus.REJECTED,
        is_active=False,
    )

    assert active_packages_count(vendor.id) == 1


def test_response_rate_metric_uses_existing_inquiry_read_ratio():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    create_inquiry(vendor=vendor, is_read=True)
    create_inquiry(vendor=vendor, is_read=False)
    create_inquiry(vendor=vendor, is_read=False)

    assert response_rate(vendor.id) == 33.33


def test_optimization_alerts_emit_codes_from_existing_metrics():
    vendor = create_vendor_profile(
        business_name="",
        description="Too short",
        contact_phone="",
    )
    create_inquiry(vendor=vendor, is_read=True)
    create_inquiry(vendor=vendor, is_read=False)
    create_inquiry(vendor=vendor, is_read=False)

    assert optimization_alerts(vendor.id) == (
        "profile_strength_low",
        "no_active_packages",
        "response_rate_low",
    )


def test_optimization_alerts_stay_empty_when_thresholds_pass():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    create_service_package(
        vendor=vendor,
        approval_status=ServicePackage.ApprovalStatus.APPROVED,
        is_active=True,
    )
    create_inquiry(vendor=vendor, is_read=True)
    create_inquiry(vendor=vendor, is_read=False)

    assert profile_strength_score(vendor.id) == 100
    assert active_packages_count(vendor.id) == 1
    assert response_rate(vendor.id) == 50.0
    assert optimization_alerts(vendor.id) == ()
