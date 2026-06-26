import uuid
import pytest
from unittest.mock import Mock

from application.vendors.commands import (
    CreateVendorProfileCommand,
    SubmitVendorForReviewCommand,
    ApproveVendorCommand,
    RejectVendorCommand,
    AddPortfolioImageCommand,
    DeletePortfolioImageCommand,
    CreateServicePackageCommand,
    UpdateServicePackageCommand,
    DeactivateServicePackageCommand,
    ActivateServicePackageCommand,
)
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import (
    VendorProfile, VendorStatus, ServiceCategory,
    PortfolioImage, ServicePackage
)


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


class TestVendorProfileCommands:
    def test_create_profile_success(self, handlers, mock_repos):
        mock_repos["vendor_repo"].get_by_user_id.return_value = None
        mock_repos["vendor_repo"].save.side_effect = lambda p: p

        cmd = CreateVendorProfileCommand(
            user_id=uuid.uuid4(),
            business_name="Test Biz",
            category="photography",
            description="We do photos",
            service_area="Kigali",
            contact_email="biz@example.com",
            contact_phone="123",
        )
        result = handlers.create_profile(cmd)

        assert result.business_name == "Test Biz"
        mock_repos["vendor_repo"].save.assert_called_once()

    def test_create_profile_duplicate_user(self, handlers, mock_repos):
        existing = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Existing",
            category=ServiceCategory.PHOTOGRAPHY,
            description="...",
            service_area="...",
            contact_email="...",
            contact_phone="...",
        )
        mock_repos["vendor_repo"].get_by_user_id.return_value = existing

        cmd = CreateVendorProfileCommand(
            user_id=existing.user_id,
            business_name="Test Biz",
            category="photography",
            description="...",
            service_area="...",
            contact_email="...",
            contact_phone="...",
        )
        with pytest.raises(ValueError, match="already has a vendor profile"):
            handlers.create_profile(cmd)

    def test_submit_for_review(self, handlers, mock_repos):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.DRAFT,
        )
        mock_repos["vendor_repo"].get_by_id.return_value = profile
        mock_repos["vendor_repo"].save.side_effect = lambda p: p

        cmd = SubmitVendorForReviewCommand(vendor_id=profile.id)
        result = handlers.submit_for_review(cmd)

        assert result.status == VendorStatus.PENDING_REVIEW.value
        mock_repos["event_dispatcher"].dispatch.assert_called_once()

    def test_approve_vendor(self, handlers, mock_repos):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
        )
        mock_repos["vendor_repo"].get_by_id.return_value = profile
        mock_repos["vendor_repo"].save.side_effect = lambda p: p

        cmd = ApproveVendorCommand(vendor_id=profile.id)
        result = handlers.approve_vendor(cmd)

        assert result.status == VendorStatus.APPROVED.value
        mock_repos["event_dispatcher"].dispatch.assert_called_once()

    def test_reject_vendor(self, handlers, mock_repos):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
        )
        mock_repos["vendor_repo"].get_by_id.return_value = profile
        mock_repos["vendor_repo"].save.side_effect = lambda p: p

        cmd = RejectVendorCommand(vendor_id=profile.id, reason="Not ready")
        result = handlers.reject_vendor(cmd)

        assert result.status == VendorStatus.REJECTED.value
        assert result.rejection_reason == "Not ready"
        mock_repos["event_dispatcher"].dispatch.assert_called_once()


class TestPortfolioCommands:
    def test_add_portfolio_image(self, handlers, mock_repos):
        mock_repos["image_repo"].list_by_vendor.return_value = []
        mock_repos["image_repo"].save.side_effect = lambda img: img

        cmd = AddPortfolioImageCommand(
            vendor_id=uuid.uuid4(),
            public_id="public123",
            secure_url="https://...",
            caption="Test image",
        )
        result = handlers.add_portfolio_image(cmd)

        assert result.secure_url == "https://..."
        assert result.caption == "Test image"
        assert result.order == 0
        mock_repos["image_repo"].save.assert_called_once()

    def test_delete_portfolio_image_rejects_wrong_vendor(self, handlers, mock_repos):
        image = PortfolioImage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            public_id="public123",
            secure_url="https://...",
        )
        mock_repos["image_repo"].get_by_id.return_value = image

        cmd = DeletePortfolioImageCommand(
            image_id=image.id,
            vendor_id=uuid.uuid4(),
        )

        with pytest.raises(ValueError, match="Image not found"):
            handlers.delete_portfolio_image(cmd)
        mock_repos["image_repo"].delete.assert_not_called()


class TestServicePackageCommands:
    def test_create_service_package(self, handlers, mock_repos):
        mock_repos["package_repo"].save.side_effect = lambda pkg: pkg

        cmd = CreateServicePackageCommand(
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive",
            price=5000.0,
            currency="RWF",
        )
        result = handlers.create_service_package(cmd)

        assert result.name == "Deluxe"
        assert result.price == 5000.0
        assert result.is_active is False
        mock_repos["package_repo"].save.assert_called_once()

    def test_update_service_package_rejects_wrong_vendor(self, handlers, mock_repos):
        package = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive",
            price=5000.0,
        )
        mock_repos["package_repo"].get_by_id.return_value = package

        cmd = UpdateServicePackageCommand(
            package_id=package.id,
            vendor_id=uuid.uuid4(),
            name="Changed",
        )

        with pytest.raises(ValueError, match="Package not found"):
            handlers.update_service_package(cmd)
        mock_repos["package_repo"].save.assert_not_called()

    def test_deactivate_service_package_rejects_wrong_vendor(self, handlers, mock_repos):
        package = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive",
            price=5000.0,
        )
        mock_repos["package_repo"].get_by_id.return_value = package

        cmd = DeactivateServicePackageCommand(
            package_id=package.id,
            vendor_id=uuid.uuid4(),
        )

        with pytest.raises(ValueError, match="Package not found"):
            handlers.deactivate_package(cmd)
        mock_repos["package_repo"].delete.assert_not_called()

    def test_activate_service_package_rejects_wrong_vendor(self, handlers, mock_repos):
        package = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive",
            price=5000.0,
        )
        mock_repos["package_repo"].get_by_id.return_value = package

        cmd = ActivateServicePackageCommand(
            package_id=package.id,
            vendor_id=uuid.uuid4(),
        )

        with pytest.raises(ValueError, match="Package not found"):
            handlers.activate_package(cmd)
        mock_repos["package_repo"].save.assert_not_called()
