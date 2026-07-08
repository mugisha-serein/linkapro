from __future__ import annotations

from domain.vendors.entities import VendorProfile, VendorStatus

from .errors import VendorOperationForbidden, VendorResourceNotFound


PORTFOLIO_MEDIA_CREATION_FORBIDDEN_STATUSES = frozenset({VendorStatus.SUSPENDED})


def ensure_vendor_can_add_portfolio_media(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorResourceNotFound("Vendor not found.", code="vendor_not_found")
    if profile.status in PORTFOLIO_MEDIA_CREATION_FORBIDDEN_STATUSES:
        raise VendorOperationForbidden(
            "Vendor cannot add portfolio media while suspended.",
            code="vendor_portfolio_media_creation_forbidden",
        )
