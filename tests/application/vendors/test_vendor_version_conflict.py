from __future__ import annotations

import uuid

import pytest

from application.vendors.errors import VendorConflict, VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers


def test_vendor_version_conflict_preserves_existing_conflict_contract_and_context():
    resource_id = uuid.uuid4()

    conflict = VendorVersionConflict(
        resource_id=resource_id,
        expected_version=3,
        actual_version=5,
    )

    assert isinstance(conflict, VendorConflict)
    assert conflict.code == "vendor_version_conflict"
    assert conflict.message == "Vendor resource has changed."
    assert str(conflict) == "Vendor resource has changed."
    assert conflict.field_errors == {}
    assert conflict.resource_id == resource_id
    assert conflict.expected_version == 3
    assert conflict.actual_version == 5


def test_assert_expected_version_raises_dedicated_conflict_with_resource_context():
    resource_id = uuid.uuid4()

    with pytest.raises(VendorVersionConflict) as exc_info:
        VendorCommandHandlers._assert_expected_version(
            resource_id=resource_id,
            actual_version=7,
            expected_version=4,
        )

    conflict = exc_info.value
    assert conflict.resource_id == resource_id
    assert conflict.expected_version == 4
    assert conflict.actual_version == 7
    assert conflict.code == "vendor_version_conflict"


def test_assert_expected_version_accepts_matching_versions():
    VendorCommandHandlers._assert_expected_version(
        resource_id=uuid.uuid4(),
        actual_version=6,
        expected_version=6,
    )
