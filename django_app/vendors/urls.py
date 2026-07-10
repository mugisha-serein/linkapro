from django.urls import path
from .contract_views import PortfolioImageView,ServicePackageActivateView,ServicePackageDetailView,ServicePackageListView,VendorProfileStatusView,VendorVerificationDocumentView
from .dashboard_summary_view import VendorDashboardSummaryView
from .vendor_dashboard_query_views import VendorAnalyticsView,VendorActivityView
from .views import VendorProfileView,VendorSubmitForReviewView,PortfolioImageReorderView,InquiryListView,PublicInquiryView,VendorBrandingMediaView,VendorCoverImageView,PublicVendorProfileView
urlpatterns=[
path("profile/",VendorProfileView.as_view(),name="vendor-profile"),
path("profile/status/",VendorProfileStatusView.as_view(),name="vendor-profile-status"),
path("profile/submi