from __future__ import annotations

from typing import Literal

from domain.vendors.inquiries.entity import Inquiry
from domain.vendors.profile.entity import VendorProfile, VendorStatus
from domain.vendors.shared.aggregate import VendorDomainError

InquiryResponseStatus = Literal["unread", "read_unanswered", "answered"]


class VendorInquiryPolicyError(VendorDomainError):
    """Raised when a vendor cannot receive public inquiries."""

    default_code = "vendor_inquiry_unavailable"


def ensure_vendor_can_receive_inquiry(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorInquiryPolicyError("Vendor not found")
    if profile.status != VendorStatus.APPROVED:
        raise VendorInquiryPolicyError("Vendor is not available for inquiries")


def response_status(inquiry: Inquiry) -> InquiryResponseStatus:
    """Classify response state from current Inquiry fields.

    The aggregate only records read state today, so there is no durable answered signal
    to distinguish answered inquiries from read-but-unanswered inquiries.
    """
    if not inquiry.is_read:
        return "unread"
    return "read_unanswered"
