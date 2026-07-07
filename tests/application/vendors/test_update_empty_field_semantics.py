from decimal import Decimal
import uuid
from unittest.mock import Mock

import pytest

from application.vendors.commands import UpdateServicePackageCommand, UpdateVendorProfileCommand
from application.vendors.handlers import VendorCommandHandlers
from domain.shared.utils import utc_now
from domain.vendors.entities import ServiceCategory, ServicePackage, VendorProfile, VendorStatus
from domain.vendors.package_rules import PackageValidationError


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


def _vendor_profile():
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        business_name="Vendor",
        category=ServiceCategory.OTHER,
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        custom_category="Original custom value",
        website="https://example.com",
        status=VendorStatus.DRAFT,
    )


def _service_package(vendor_id):
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Standard package",
        description="A clear standard event package with defined deliverables.",
        price=Decimal("5000.00"),
        currency="RWF",
        package_tier="standard",
        approval_status="approved",
        last_approved_at=utc_now(),
    )


def test_update_profile_rejects_blank_required_field(handlers, mock_repos):
    profile = _vendor_profile()
    mock_repos["vendor_repo"].get_by_id.return_value = profile

    with pytest.raises(ValueError, match="business_name"):
        handlers.update_profile(UpdateVendorProfileCommand(vendor_id=profile.id, business_name=""))

    assert profile.business_name == "Vendor"
    mock_repos["vendor_repo"].save.assert_not_called()


def test_update_profile_allows_clearing_optional_fields(handlers, mock_repos):
    profile = _vendor_profile()
    mock_repos["vendor_repo"].get_by_id.return_value = profile
    mock_repos["vendor_repo"].save.side_effect = lambda updated: updated

    result = handlers.update_profile(
        UpdateVendorProfileCommand(vendor_id=profile.id, custom_category="", website="")
    )

    assert result.custom_category == ""
    assert result.website == ""
    mock_repos["vendor_repo"].save.assert_called_once()


def test_update_service_package_rejects_blank_name_instead_of_ignoring_it(handlers, mock_repos):
    vendor_id = uuid.uuid4()
    package = _service_package(vendor_id)
    mock_repos["package_repo"].get_by_id.return_value = package

    with pytest.raises(PackageValidationError) as exc_info:
        handlers.update_service_package(
            UpdateServicePackageCommand(package_id=package.id, vendor_id=vendor_id, name="")
    )

    assert exc_info.value.errors["name"] == ["Package name is required."]
    assert package.name == "Standard package"
    mock_repos["package_repo"].save.assert_not_called()
