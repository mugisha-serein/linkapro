from django.urls import path
from .views import inquiries as inquiry_v
from .views import profile as profile_v
urlpatterns = [
path("inquiries/", inquiry_v.InquiryListView.as_view(), name="inquiry-list"),
path("public/<uuid:vendor_id>/", profile_v.PublicVendorProfileView.as_view(), name="public-vendor-profile"),
path("public/<uuid:vendor_id>/inquiries/", inquiry_v.PublicInquiryView.as_view(), name="public-inquiries"),
path("public/<uuid:vendor_id>/inquiry/", inquiry_v.PublicInquiryView.as_view(), name="public-inquiry"),
]
