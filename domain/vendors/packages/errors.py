from __future__ import annotations

from domain.vendors.shared.aggregate import VendorDomainError

class PackageValidationError(VendorDomainError):
    default_code = "service_package_invalid"

class InvalidPackageTransition(VendorDomainError):
    default_code = "service_package_transition_invalid"
