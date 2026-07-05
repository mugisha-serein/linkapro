from django.urls import path
from .csrf_views import VendorProfileView
from .contract_views import (
    PortfolioImageView,
    ServicePackageActivateView,
    ServicePackageDetailView,
    ServicePackageListView,
    VendorProfileStatusView,
    VendorVerificationDocumentView,
)
from .views import (
    VendorSubmitForReviewView,
    PortfolioImageReorderView,
    InquiryListView,
    PublicInquiryView,
    VendorDashboardSummaryView,
    VendorAnalyticsView,
    VendorActivityView,
    VendorBrandingMediaView,
    VendorCoverImageView,
    PublicVendorProfileView,
)

urlpatterns = [
    path("profile/", VendorProfileView.as_view(), name="vendor-profile"),
    path("profile/status/", VendorProfileStatusView.as_view(), name="vendor-profile-status"),
    path("profile/submit/", VendorSubmitForReviewView.as_view(), name="vendor-submit"),
    path("profile/media/profile-image/", VendorBrandingMediaView.as_view(), name="vendor-profile-image"),
    path("profile/media/cover-image/", VendorCoverImageView.as_view(), name="vendor-cover-image"),
    path("portfolio/", PortfolioImageView.as_view(), name="portfolio-list"),
    path("portfolio/<uuid:image_id>/", PortfolioImageView.as_view(), name="portfolio-detail"),
    path("portfolio/reorder/", PortfolioImageReorderView.as_view(), name="portfolio-reorder"),
    path("profile/verification-documents/", VendorVerificationDocumentView.as_view(), name="vendor-verification-documents"),
    path("packages/", ServicePackageListView.as_view(), name="package-list"),
    path("packages/<uuid:package_id>/", ServicePackageDetailView.as_view(), name="package-detail"),
    path("packages/<uuid:package_id>/activate/", ServicePackageActivateView.as_view(), name="package-activate"),
    path("inquiries/", InquiryListView.as_view(), name="inquiry-list"),
    path("dashboard-summary/", VendorDashboardSummaryView.as_view(), name="vendor-dashboard-summary"),
    path("analytics/", VendorAnalyticsView.as_view(), name="vendor-analytics"),
    path("activity/", VendorActivityView.as_view(), name="vendor-activity"),
    path("public/<uuid:vendor_id>/", PublicVendorProfileView.as_view(), name="public-vendor-profile"),
    path("public/<uuid:vendor_id>/inquiries/", PublicInquiryView.as_view(), name="public-inquiries"),
    path("public/<uuid:vendor_id>/inquiry/", PublicInquiryView.as_view(), name="public-inquiry"),
]
