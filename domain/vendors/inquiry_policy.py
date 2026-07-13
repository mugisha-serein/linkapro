from __future__ import annotations

from domain.vendors.entities import VendorProfile, VendorStatus
from domain.vendors.errors import VendorDomainError


class VendorInquiryPolicyError(VendorDomainError):
    """Raised when a vendor cannot receive public inquiries."""

    default_code = "vendor_inquiry_unavailable"


def ensure_vendor_can_receive_inquiry(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorInquiryPolicyError("Vendor not found")
    if profile.status != VendorStatus.APPROVED:
        raise VendorInquiryPolicyError("Vendor is not available for inquiries")
