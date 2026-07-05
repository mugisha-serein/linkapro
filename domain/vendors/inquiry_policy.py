from __future__ import annotations

from domain.vendors.entities import VendorProfile, VendorStatus


class VendorInquiryPolicyError(ValueError):
    """Raised when a vendor cannot receive public inquiries."""


def ensure_vendor_can_receive_inquiry(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorInquiryPolicyError("Vendor not found")
    if profile.status != VendorStatus.APPROVED:
        raise VendorInquiryPolicyError("Vendor is not available for inquiries")
