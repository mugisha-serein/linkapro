from __future__ import annotations


class VendorDomainError(ValueError):
    default_code = "vendor_domain_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.field_errors = field_errors or {}
        self.errors = self.field_errors
        super().__init__(message or self.code)


class VendorProfileValidationError(VendorDomainError):
    default_code = "vendor_profile_invalid"


class InvalidVendorTransition(VendorDomainError):
    default_code = "vendor_transition_invalid"


class PackageValidationError(VendorDomainError):
    default_code = "service_package_invalid"


class InvalidPackageTransition(VendorDomainError):
    default_code = "service_package_transition_invalid"


class PortfolioValidationError(VendorDomainError):
    default_code = "portfolio_media_invalid"


class InvalidPortfolioTransition(VendorDomainError):
    default_code = "portfolio_media_transition_invalid"


class InquiryValidationError(VendorDomainError):
    default_code = "inquiry_invalid"


class ConcurrentVendorUpdate(VendorDomainError):
    default_code = "vendor_concurrent_update"
