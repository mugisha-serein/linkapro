from __future__ import annotations

from domain.vendors.shared.aggregate import VendorDomainError

class VendorProfileValidationError(VendorDomainError):
    default_code = "vendor_profile_invalid"

class InvalidVendorTransition(VendorDomainError):
    default_code = "vendor_transition_invalid"
