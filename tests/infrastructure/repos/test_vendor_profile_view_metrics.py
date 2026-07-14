from datetime import date

import pytest

from django_app.vendors.models import VendorProfileViewed
from infrastructure.repos.analytics import metrics
from infrastructure.repos.analytics.metrics import log_profile_view, total_views_trend, views_by_month, visibility_trend
from tests.factories import create_vendor_profile

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
