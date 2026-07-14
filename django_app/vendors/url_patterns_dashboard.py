from django.urls import path
from .views.analytics import (
    VendorActivityView,
    VendorAnalyticsView,
    VendorDashboardSummaryView,
    VendorPortfolioQualityTrendView,
    VendorSecurityActionsView,
    VendorViewsTrendView,
)
urlpatterns = [
    path("dashboard-summary/", VendorDashboardSummaryView.as_view(), name="vendor-dashboard-summary"),
    path("analytics/", VendorAnalyticsView.as_view(), name="vendor-analytics"),
    path("analytics/views-trend/", VendorViewsTrendView.as_view(), name="vendor-analytics-views-trend"),
    path(
        "analytics/portfolio-quality-trend/",
        VendorPortfolioQualityTrendView.as_view(),
        name="vendor-analytics-portfolio-quality-trend",
    ),
    path("analytics/security-actions/", VendorSecurityActionsView.as_view(), name="vendor-analytics-security-actions"),
    path("activity/", VendorActivityView.as_view(), name="vendor-activity"),
]
