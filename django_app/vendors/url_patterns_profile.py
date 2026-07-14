from django.urls import path
from .views import profile as v
urlpatterns=[
path("profile/",v.VendorProfileView.as_view(),name="vendor-profile"),
path("profile/status/",v.VendorProfileStatusView.as_view(),name="vendor-profile-status"),
path("profile/submit/",v.VendorSubmitForReviewView.as_view(),name="vendor-submit"),
path("profile/media/profile-image/",v.VendorBrandingMediaView.as_view(),name="vendor-profile-image"),
path("profile/media/cover-image/",v.VendorCoverImageView.as_view(),name="vendor-cover-image"),
path("profile/verification-documents/",v.VendorVerificationDocumentView.as_view(),name="vendor-verification-documents"),
]
