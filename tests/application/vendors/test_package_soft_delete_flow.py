from decimal import Decimal
import uuid
from unittest.mock import Mock

import pytest

from application.vendors.commands import DeactivateServicePackageCommand
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import ServicePackage


@pytest.fixture
def mock_repos():
    return {
        "vendor_repo": Mock(),
        "image_repo": Mock(),
        "package_repo": Mock(),
        "inquiry_repo": Mock(),
        "event_dispatcher": Mock(),
    }


@pytest.fixture
def handlers(mock_repos):
    return VendorCommandHandlers(
        vendor_repo=mock_repos["vendor_repo"],
        image_repo=mock_repos["image_repo"],
        package_repo=mock_repos["package_repo"],
        inquiry_repo=mock_repos["inquiry_repo"],
        event_dispatcher=mock_repos["event_dispatcher"],
    )


def _service_package(vendor_id, *, is_active=True, is_deleted=False):
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Standard package",
        description="A standard vendor package with clear event deliverables.",
        price=Decimal("5000.00"),
        currency="RWF",
        package_tier="standard",
        approval_status="approved",
        is_active=is_active,
        is_deleted=is_deleted,
    )


def test_deactivate_package_delegates_soft_delete_to_repository_once(handlers, mock_repos):
    vendor_id = uuid.uuid4()
    deleted_by_id = uuid.uuid4()
    package = _service_package(vendor_id)
    deleted_package = _service_package(vendor_id, is_active=False, is_deleted=True)
    deleted_package.id = package.id

    mock_repos["package_repo"].get_by_id.return_value = package
    mock_repos["package_repo"].delete.return_value = deleted_package

    result = handlers.deactivate_package(
        DeactivateServicePackageCommand(
            package_id=package.id,
            vendor_id=vendor_id,
            deleted_by_id=deleted_by_id,
        )
    )

    assert result.id == package.id
    assert result.is_active is False
    assert result.is_deleted is True
    mock_repos["package_repo"].save.assert_not_called()
    mock_repos["package_repo"].delete.assert_called_once_with(package.id, deleted_by_id=deleted_by_id)


def test_deactivate_package_rejects_when_repository_delete_returns_missing(handlers, mock_repos):
    vendor_id = uuid.uuid4()
    package = _service_package(vendor_id)

    mock_repos["package_repo"].get_by_id.return_value = package
    mock_repos["package_repo"].delete.return_value = None

    with pytest.raises(ValueError, match="Package not found"):
        handlers.deactivate_package(
            DeactivateServicePackageCommand(package_id=package.id, vendor_id=vendor_id)
        )

    mock_repos["package_repo"].save.assert_not_called()
