from __future__ import annotations

from dataclasses import MISSING, fields
import uuid

import pytest

from application.vendors.packages.commands import DeactivateServicePackageCommand
from application.vendors.shared.commands import AuthenticatedActor


def test_deactivate_service_package_command_contains_only_current_use_case_inputs():
    command_fields = fields(DeactivateServicePackageCommand)

    assert tuple(field.name for field in command_fields) == (
        "actor",
        "vendor_id",
        "package_id",
        "expected_version",
    )
    assert all(field.default is MISSING for field in command_fields)
    assert "deleted_by_id" not in DeactivateServicePackageCommand.__annotations__


def test_deactivate_service_package_command_rejects_removed_deleted_by_id_argument():
    with pytest.raises(TypeError, match="deleted_by_id"):
        DeactivateServicePackageCommand(
            actor=AuthenticatedActor(user_id=uuid.uuid4()),
            vendor_id=uuid.uuid4(),
            package_id=uuid.uuid4(),
            expected_version=3,
            deleted_by_id=uuid.uuid4(),
        )


def test_deactivate_service_package_command_runtime_behavior_is_unchanged_without_attribution():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    package_id = uuid.uuid4()

    command = DeactivateServicePackageCommand(
        actor=actor,
        vendor_id=vendor_id,
        package_id=package_id,
        expected_version=4,
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.package_id == package_id
    assert command.expected_version == 4
    assert not hasattr(command, "deleted_by_id")
