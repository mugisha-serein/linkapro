from django.urls import path
from . import views as v
urlpatterns = [
    path("inquiries/", v.InquiryListView.as_view(), name="inquiry-list"),
    path("public/<uuid:vendor_id>/", v.PublicVendorProfileView.as_view(), name="public-vendor-profile"),
    path("public/<uuid:vendor_id>/inquiries/", v.PublicInquiryView.as_view(), name="public-inquiries"),
    path("public/<uuid:vendor_id>/inquiry/", v.PublicInquiryView.as_view(), name="public-inquiry"),
]
