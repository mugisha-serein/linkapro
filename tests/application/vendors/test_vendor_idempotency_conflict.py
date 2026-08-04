from __future__ import annotations

import uuid

import pytest

from application.vendors.errors import (
    VendorConflict,
    VendorIdempotencyConflict,
    VendorVersionConflict,
)
from application.vendors.handlers import VendorCommandHandlers


def test_vendor_idempotency_conflict_has_stable_code_and_message():
    error = VendorIdempotencyConflict()

    assert isinstance(error, VendorConflict)
    assert type(error) is VendorIdempotencyConflict
    assert error.code == "vendor_idempotency_conflict"
    assert error.message == "Idempotency key was already used with a different payload."
    assert str(error) == error.message
    assert error.field_errors == {}


def test_ordinary_version_conflict_remains_vendor_version_conflict():
    resource_id = uuid.uuid4()

    with pytest.raises(VendorVersionConflict) as exc_info:
        VendorCommandHandlers._assert_expected_version(
            resource_id=resource_id,
            actual_version=4,
            expected_version=3,
        )

    error = exc_info.value
    assert type(error) is VendorVersionConflict
    assert not isinstance(error, VendorIdempotencyConflict)
    assert error.code == "vendor_version_conflict"
    assert error.resource_id == resource_id
    assert error.expected_version == 3
    assert error.actual_version == 4
