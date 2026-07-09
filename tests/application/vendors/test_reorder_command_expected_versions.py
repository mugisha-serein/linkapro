from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import (
    AuthenticatedActor,
    ReorderPortfolioImagesCommand,
    ResourceVersion,
)
from application.vendors.errors import InvalidVendorCommand


def test_reorder_command_rejects_duplicate_resource_ids_in_expected_versions():
    vendor_id = uuid.uuid4()
    image_id = uuid.uuid4()

    with pytest.raises(InvalidVendorCommand) as exc_info:
        ReorderPortfolioImagesCommand(
            actor=AuthenticatedActor(user_id=uuid.uuid4()),
            vendor_id=vendor_id,
            image_ids_in_order=(image_id,),
            expected_versions=(
                ResourceVersion(resource_id=image_id, expected_version=2),
                ResourceVersion(resource_id=image_id, expected_version=3),
            ),
        )

    assert exc_info.value.field_errors == {
        "expected_versions": ["Duplicate resource IDs are not allowed."]
    }


def test_reorder_command_preserves_unique_expected_version_collection_order():
    vendor_id = uuid.uuid4()
    first_image_id = uuid.uuid4()
    second_image_id = uuid.uuid4()
    expected_versions = (
        ResourceVersion(resource_id=second_image_id, expected_version=4),
        ResourceVersion(resource_id=first_image_id, expected_version=1),
    )

    command = ReorderPortfolioImagesCommand(
        actor=AuthenticatedActor(user_id=uuid.uuid4()),
        vendor_id=vendor_id,
        image_ids_in_order=(first_image_id, second_image_id),
        expected_versions=expected_versions,
    )

    assert command.expected_versions == expected_versions
