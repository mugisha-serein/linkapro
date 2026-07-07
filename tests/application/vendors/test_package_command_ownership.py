import uuid
from unittest.mock import Mock

import pytest

from application.vendors.commands import (
    ActivateServicePackageCommand,
    DeactivateServicePackageCommand,
    UpdateServicePackageCommand,
)
from application.vendors.cooldown_handlers import VendorCooldownCommandHandlers
from domain.vendors.entities import ServicePackage


@pytest.fixture
def command_handler():
    repos = {
        "vendor_repo": Mock(),
        "image_repo": Mock(),
        "package_repo": Mock(),
        "inquiry_repo": Mock(),
        "event_dispatcher": Mock(),
    }
    handler = VendorCooldownCommandHandlers(**repos)
    return handler, repos


def package_for(vendor_id):
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Owned Package",
        description="Package owned by one vendor with clear deliverables.",
        price="100000.00",
        approval_status="waiting_approval",
        is_active=False,
    )


def test_update_package_rejects_missing_vendor_id(command_handler):
    handler, repos = command_handler
    package = package_for(uuid.uuid4())
    repos["package_repo"].get_by_id.return_value = package

    cmd = UpdateServicePackageCommand(package_id=package.id, name="Changed")

    with pytest.raises(ValueError, match="Package not found"):
        handler.update_service_package(cmd)
    repos["package_repo"].save.assert_not_called()


def test_update_package_rejects_wrong_vendor_id(command_handler):
    handler, repos = command_handler
    package = package_for(uuid.uuid4())
    repos["package_repo"].get_by_id.return_value = package

    cmd = UpdateServicePackageCommand(package_id=package.id, vendor_id=uuid.uuid4(), name="Changed")

    with pytest.raises(ValueError, match="Package not found"):
        handler.update_service_package(cmd)
    repos["package_repo"].save.assert_not_called()


def test_deactivate_package_rejects_missing_vendor_id(command_handler):
    handler, repos = command_handler
    package = package_for(uuid.uuid4())
    repos["package_repo"].get_by_id.return_value = package

    cmd = DeactivateServicePackageCommand(package_id=package.id, deleted_by_id=uuid.uuid4())

    with pytest.raises(ValueError, match="Package not found"):
        handler.deactivate_package(cmd)
    repos["package_repo"].delete.assert_not_called()


def test_deactivate_package_rejects_wrong_vendor_id(command_handler):
    handler, repos = command_handler
    package = package_for(uuid.uuid4())
    repos["package_repo"].get_by_id.return_value = package

    cmd = DeactivateServicePackageCommand(
        package_id=package.id,
        vendor_id=uuid.uuid4(),
        deleted_by_id=uuid.uuid4(),
    )

    with pytest.raises(ValueError, match="Package not found"):
        handler.deactivate_package(cmd)
    repos["package_repo"].delete.assert_not_called()


def test_activate_package_rejects_missing_vendor_id(command_handler):
    handler, repos = command_handler
    package = package_for(uuid.uuid4())
    repos["package_repo"].get_by_id.return_value = package

    cmd = ActivateServicePackageCommand(package_id=package.id)

    with pytest.raises(ValueError, match="Package not found"):
        handler.activate_package(cmd)
    repos["package_repo"].save.assert_not_called()
