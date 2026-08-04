from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal
from typing import get_type_hints
import uuid

from application.vendors.dtos import ServicePackageDTO
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import ServicePackage


def _package(
    *,
    last_approved_at=None,
    last_vendor_public_edit_at=None,
    next_vendor_edit_allowed_at=None,
) -> ServicePackage:
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        name="Premium Package",
        description="Complete event service package.",
        price=Decimal("250000"),
        currency="RWF",
        package_tier="premier",
        approval_status="waiting_approval",
        rejection_reason=None,
        is_active=False,
        is_deleted=False,
        deleted_at=None,
        last_approved_at=last_approved_at,
        last_vendor_public_edit_at=last_vendor_public_edit_at,
        next_vendor_edit_allowed_at=next_vendor_edit_allowed_at,
        version=3,
    )


def test_service_package_dto_exposes_three_nullable_cooldown_datetimes():
    hints = get_type_hints(ServicePackageDTO)
    field_names = tuple(field.name for field in fields(ServicePackageDTO))

    assert field_names[-4:] == (
        "last_approved_at",
        "last_vendor_public_edit_at",
        "next_vendor_edit_allowed_at",
        "version",
    )
    assert hints["last_approved_at"] == datetime | None
    assert hints["last_vendor_public_edit_at"] == datetime | None
    assert hints["next_vendor_edit_allowed_at"] == datetime | None


def test_package_to_dto_preserves_null_cooldown_timestamps():
    package = _package()

    dto = VendorCommandHandlers._to_package_dto(package)

    assert dto.last_approved_at is None
    assert dto.last_vendor_public_edit_at is None
    assert dto.next_vendor_edit_allowed_at is None


def test_package_to_dto_preserves_exact_cooldown_timestamps():
    last_approved_at = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    last_vendor_public_edit_at = datetime(2026, 7, 8, 14, 30, tzinfo=timezone.utc)
    next_vendor_edit_allowed_at = datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc)
    package = _package(
        last_approved_at=last_approved_at,
        last_vendor_public_edit_at=last_vendor_public_edit_at,
        next_vendor_edit_allowed_at=next_vendor_edit_allowed_at,
    )

    dto = VendorCommandHandlers._to_package_dto(package)

    assert dto.last_approved_at is last_approved_at
    assert dto.last_vendor_public_edit_at is last_vendor_public_edit_at
    assert dto.next_vendor_edit_allowed_at is next_vendor_edit_allowed_at
    assert dto.version == package.version
