from django.urls import path
from .contract_views import (
    PortfolioImageView,
    ServicePackageActivateView,
    ServicePackageDetailView,
    ServicePackageListView,
    VendorProfileStatusView,
    VendorVerificationDocumentView,
)
from .dashboard_summary_view import VendorDashboardSummaryView
from .vendor_dashboard_query_views import VendorAnalyticsView, VendorActivityView
from .views impor