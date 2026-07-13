from django.urls import path
from .views.analytics import VendorActivityView, VendorAnalyticsView, VendorDashboardSummaryView
urlpatterns = [
    path("dashboard-summary/", VendorDashboardSummaryView.as_view(), name="vendor-dashboard-summary"),
    path("analytics/", VendorAnalyticsView.as_view(), name="vendor-analytics"),
    path("activity/", VendorActivityView.as_view(), name="vendor-activity"),
]
