from rest_framework.throttling import ScopedRateThrottle


class PublicVendorInquiryThrottle(ScopedRateThrottle):
    scope = "public_vendor_inquiry"
