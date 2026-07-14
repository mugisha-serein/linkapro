from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from domain.shared.utils import utc_now
from domain.vendors.packages.errors import PackageValidationError
from domain.vendors.packages.rules import PackageEditCooldownError, ensure_vendor_package_edit_allowed, mark_vendor_package_public_edit, package_public_fields_changed


def package(**overrides):
    now = utc_now()
    data = {
        "name": "Standard package",
        "description": "A clear standard event package with defined deliverables.",
        "price": Decimal("1000.00"),
        "currency": "RWF",
        "package_tier": "standard",
        "approval_status": "approved",
        "updated_at": now,
        "last_approved_at": now,
        "last_vendor_public_edit_at": None,
        "next_vendor_edit_allowed_at": None,
        "rejection_reason": None,
        "is_active": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_naive_timestamps_are_rejected():
    pkg = package(last_approved_at=datetime(2025, 1, 1))

    with pytest.raises(PackageValidationError) as exc_info:
        ensure_vendor_package_edit_allowed(pkg, public_fields_changed=True, now=utc_now())

    assert "last_approved_at" in exc_info.value.field_errors


def test_whitespace_only_changes_do_not_reset_approval():
    pkg = package()

    changed = package_public_fields_changed(
        pkg,
        name=" Standard package ",
        description=" A clear standard event package with defined deliverables. ",
        price="1000.00",
        currency=" rwf ",
        package_tier=" Standard ",
    )
    markers = mark_vendor_package_public_edit(pkg, now=utc_now(), public_fields_changed=changed)

    assert changed is False
    assert markers == {}
    assert pkg.approval_status == "approved"
    assert pkg.is_active is True
    assert pkg.next_vendor_edit_allowed_at is None


def test_real_changes_return_markers_without_mutating_package_after_cooldown():
    now = utc_now()
    pkg = package(last_approved_at=now - timedelta(days=16))
    original = vars(pkg).copy()

    markers = mark_vendor_package_public_edit(pkg, now=now, public_fields_changed=True)

    assert markers == {
        "approval_status": "waiting_approval",
        "rejection_reason": None,
        "is_active": False,
        "last_vendor_public_edit_at": now,
        "next_vendor_edit_allowed_at": now + timedelta(days=15),
    }
    assert vars(pkg) == original


def test_real_changes_still_apply_existing_cooldown():
    now = utc_now()
    pkg = package(last_approved_at=now - timedelta(days=1))

    assert package_public_fields_changed(pkg, name="Changed package") is True
    with pytest.raises(PackageEditCooldownError) as exc_info:
        ensure_vendor_package_edit_allowed(pkg, public_fields_changed=True, now=now)

    assert exc_info.value.next_allowed_at == pkg.last_approved_at + timedelta(days=15)


def test_failed_cooldown_operation_does_not_mutate_package():
    now = utc_now()
    pkg = package(
        last_vendor_public_edit_at=now,
        next_vendor_edit_allowed_at=now - timedelta(days=1),
    )
    original = vars(pkg).copy()

    with pytest.raises(PackageValidationError):
        mark_vendor_package_public_edit(pkg, now=now, public_fields_changed=True)

    assert vars(pkg) == original
