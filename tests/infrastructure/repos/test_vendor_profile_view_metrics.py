from datetime import date

import pytest

from django_app.vendors.models import VendorProfileViewed
from infrastructure.repos.analytics import metrics
from infrastructure.repos.analytics.metrics import log_profile_view, total_views_trend
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
