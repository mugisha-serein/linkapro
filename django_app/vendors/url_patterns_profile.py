from django.urls import path
from . import contract_views as c
from .views import profile as v
urlpatterns=[
path("profile/",v.VendorProfileView.as_view(),name="vendor-profile"),
path("profile/status/",c.VendorProfileStatusView.as_view(),name="vendor-profile-status"),
path("profile/submit/",v.VendorSubmitForReviewView.as_view(),name="vendor-submit"),
path("profile/media/profile-image/",v.VendorBrandingMediaView.as_view(),name="vendor-profile-image"),
path("profile/media/cover-image/",v.VendorCoverImageView.as_view(),name="vendor-cover-image"),
path("profile/verification-documents/",c.VendorVerificationDocumentView.as_view(),name="vendor-verification-documents"),
]
