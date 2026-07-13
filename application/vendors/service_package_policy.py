from __future__ import annotations

from domain.vendors.entities import VendorProfile, VendorStatus

from .errors import VendorOperationForbidden, VendorResourceNotFound


SERVICE_PACKAGE_CREATION_ALLOWED_STATUSES = frozenset({VendorStatus.APPROVED})


def ensure_vendor_can_create_service_package(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorResourceNotFound("Vendor not found.", code="vendor_not_found")
    if profile.status not in SERVICE_PACKAGE_CREATION_ALLOWED_STATUSES:
        raise VendorOperationForbidden(
            "Vendor must be approved before creating service packages.",
            code="vendor_service_package_creation_forbidden",
        )
