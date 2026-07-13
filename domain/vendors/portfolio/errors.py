from __future__ import annotations

from domain.vendors.shared.aggregate import VendorDomainError

class PortfolioValidationError(VendorDomainError):
    default_code = "portfolio_media_invalid"

class InvalidPortfolioTransition(VendorDomainError):
    default_code = "portfolio_media_transition_invalid"
