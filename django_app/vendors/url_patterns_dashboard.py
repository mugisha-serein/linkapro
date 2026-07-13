from django.urls import path
from .dashboard_summary_view import VendorDashboardSummaryView
from .vendor_dashboard_query_views import VendorActivityView, VendorAnalyticsView
urlpatterns = [
    path("dashboard-summary/", VendorDashboardSummaryView.as_view(), name="vendor-dashboard-summary"),
    path("analytics/", VendorAnalyticsView.as_view(), name="vendor-analytics"),
    path("activity/", VendorActivityView.as_view(), name="vendor-activity"),
]
