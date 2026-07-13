from __future__ import annotations

from domain.vendors.shared.aggregate import VendorDomainError

class InquiryValidationError(VendorDomainError):
    default_code = "inquiry_invalid"
