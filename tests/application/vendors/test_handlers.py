import uuid
from datetime import timedelta
import pytest
from unittest.mock import Mock

from application.vendors.commands import (
    CreateVendorProfileCommand,
    SubmitVendorForReviewCommand,
    ApproveVendorCommand,
    RejectVendorCommand,
    AddPortfolioImageCommand,
    DeletePortfolioImageCommand,
    ReorderPortfolioImagesCommand,
    CreateServicePackageCommand,
    UpdateServicePackageCommand,
    DeactivateServicePackageCommand,
    ActivateServicePackageCommand,
)
from application.vendors.handlers import VendorCommandHandlers, VendorQueryHandlers
from domain.shared.utils import utc_now
from domain.vendors.entities import (
    VendorProfile, VendorStatus, ServiceCategory,
    PortfolioImage, ServicePackage, Inquiry
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


@pytest.fixture
def query_handlers(mock_repos):
    return VendorQueryHandlers(
        vendor_repo=mock_repos["vendor_repo"],
        image_repo=mock_repos["image_repo"],
        package_repo=mock_repos["package_repo"],
        inquiry_repo=mock_repos["inquiry_repo"],
    )


def _portfolio_image(vendor_id, *, order=0):
    return PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        public_id=f"public-{order}",
        secure_url="https://example.com/image.jpg",
        order=order,
    )


def _vendor_profile(vendor_id):
    now = utc_now()
    return VendorProfile(
        id=vendor_id,
        user_id=uuid.uuid4(),
        business_name="Metrics Vendor",
        category=ServiceCategory.CATERING,
        description="Food and event catering",
        service_area="Kigali",
        contact_email="metrics@example.com",
        contact_phone="+250700000000",
        status=VendorStatus.APPROVED,
        submitted_at=now,
        approved_at=now,
    )


def _service_package(vendor_id, *, status="approved", active=True):
    now = utc_now()
    lifecycle = {}
    if status == "approved":
        lifecycle["last_approved_at"] = now
    if status == "rejected":
        lifecycle["rejection_reason"] = "Needs more detail"
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Package",
        description="Useful vendor package with clear event deliverables.",
        price=5000.0,
        approval_status=status,
        is_active=active,
        **lifecycle,
    )


def _inquiry(vendor_id, *, is_read=False, created_at=None):
    return Inquiry(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you help with my event?",
        is_read=is_read,
        created_at=created_at or utc_now(),
    )


class TestVendorProfileCommands:
    def test_create_profile_success(self, handlers, mock_repos):
        mock_repos["vendor_repo"].get_by_user_id.return_value = None
        mock_repos["vendor_repo"].save.side_effect = lambda p: p

        cmd = CreateVendorProfileCommand(
            user_id=uuid.uuid4(),
            business_name="Test Biz",
            category="photography",
            description="We do professional event photography.",
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
            description="Existing vendor profile with complete details.",
            service_area="Kigali",
            contact_email="existing@example.com",
            contact_phone="+250700000000",
        )
        mock_repos["vendor_repo"].get_by_user_id.return_value = existing

        cmd = CreateVendorProfileCommand(
            user_id=existing.user_id,
            business_name="Test Biz",
            category="photography",
            description="Complete duplicate vendor profile details.",
            service_area="Kigali",
            contact_email="duplicate@example.com",
            contact_phone="+250700000000",
        )
        with pytest.raises(ValueError, match="already has a vendor profile"):
            handlers.create_profile(cmd)

    def test_submit_for_review(self, handlers, mock_repos):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food and event catering services.",
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
            description="Food and event catering services.",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
            submitted_at=utc_now(),
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
            description="Food and event catering services.",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
            submitted_at=utc_now(),
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

    def test_reorder_portfolio_images_reorders_exact_vendor_set(self, handlers, mock_repos):
        vendor_id = uuid.uuid4()
        first = _portfolio_image(vendor_id, order=0)
        second = _portfolio_image(vendor_id, order=1)
        mock_repos["image_repo"].list_by_vendor.return_value = [first, second]
        mock_repos["image_repo"].save.side_effect = lambda img: img

        result = handlers.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(vendor_id=vendor_id, image_ids_in_order=[second.id, first.id])
        )

        assert [item.id for item in result] == [second.id, first.id]
        assert second.order == 0
        assert first.order == 1
        assert mock_repos["image_repo"].save.call_count == 2

    def test_reorder_portfolio_images_rejects_duplicate_ids(self, handlers, mock_repos):
        vendor_id = uuid.uuid4()
        first = _portfolio_image(vendor_id, order=0)
        second = _portfolio_image(vendor_id, order=1)
        mock_repos["image_repo"].list_by_vendor.return_value = [first, second]

        with pytest.raises(ValueError, match="duplicate"):
            handlers.reorder_portfolio_images(
                ReorderPortfolioImagesCommand(vendor_id=vendor_id, image_ids_in_order=[first.id, first.id])
            )
        mock_repos["image_repo"].save.assert_not_called()

    def test_reorder_portfolio_images_rejects_missing_vendor_image(self, handlers, mock_repos):
        vendor_id = uuid.uuid4()
        first = _portfolio_image(vendor_id, order=0)
        second = _portfolio_image(vendor_id, order=1)
        mock_repos["image_repo"].list_by_vendor.return_value = [first, second]

        with pytest.raises(ValueError, match="every image"):
            handlers.reorder_portfolio_images(
                ReorderPortfolioImagesCommand(vendor_id=vendor_id, image_ids_in_order=[first.id])
            )
        mock_repos["image_repo"].save.assert_not_called()

    def test_reorder_portfolio_images_rejects_foreign_image_id(self, handlers, mock_repos):
        vendor_id = uuid.uuid4()
        first = _portfolio_image(vendor_id, order=0)
        mock_repos["image_repo"].list_by_vendor.return_value = [first]

        with pytest.raises(ValueError, match="every image"):
            handlers.reorder_portfolio_images(
                ReorderPortfolioImagesCommand(vendor_id=vendor_id, image_ids_in_order=[first.id, uuid.uuid4()])
            )
        mock_repos["image_repo"].save.assert_not_called()


class TestServicePackageCommands:
    def test_create_service_package(self, handlers, mock_repos):
        mock_repos["package_repo"].add.side_effect = lambda pkg: pkg

        cmd = CreateServicePackageCommand(
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive package with clear deliverables.",
            price=5000.0,
            currency="RWF",
        )
        result = handlers.create_service_package(cmd)

        assert result.name == "Deluxe"
        assert result.price == 5000.0
        assert result.is_active is False
        mock_repos["package_repo"].add.assert_called_once()

    def test_update_service_package_rejects_wrong_vendor(self, handlers, mock_repos):
        package = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Deluxe",
            description="All inclusive package with clear deliverables.",
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
            description="All inclusive package with clear deliverables.",
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
            description="All inclusive package with clear deliverables.",
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


class TestVendorDashboardMetrics:
    def test_dashboard_summary_uses_real_vendor_counts(self, query_handlers, mock_repos):
        vendor_id = uuid.uuid4()
        mock_repos["vendor_repo"].get_by_id.return_value = _vendor_profile(vendor_id)
        mock_repos["inquiry_repo"].list_by_vendor.return_value = [
            _inquiry(vendor_id, is_read=False),
            _inquiry(vendor_id, is_read=True),
        ]
        mock_repos["package_repo"].list_by_vendor.return_value = [
            _service_package(vendor_id, status="approved", active=True),
            _service_package(vendor_id, status="waiting_approval", active=False),
        ]
        mock_repos["image_repo"].list_by_vendor.return_value = [
            _portfolio_image(vendor_id, order=0),
            _portfolio_image(vendor_id, order=1),
        ]

        summary = query_handlers.get_dashboard_summary(vendor_id)

        assert summary["planner_requests"] == 2
        assert summary["unread_inquiries"] == 1
        assert summary["active_packages"] == 1
        assert summary["portfolio_count"] == 2
        assert summary["total_packages"] == 2
        assert summary["pending_packages"] == 1
        assert summary["account_status"] == VendorStatus.APPROVED.value

    def test_analytics_uses_real_counts_and_marks_unavailable_metrics(self, query_handlers, mock_repos):
        vendor_id = uuid.uuid4()
        now = utc_now()
        mock_repos["vendor_repo"].get_by_id.return_value = _vendor_profile(vendor_id)
        mock_repos["inquiry_repo"].list_by_vendor.return_value = [
            _inquiry(vendor_id, is_read=True, created_at=now),
            _inquiry(vendor_id, is_read=False, created_at=now),
            _inquiry(vendor_id, is_read=False, created_at=now - timedelta(days=40)),
        ]
        mock_repos["package_repo"].list_by_vendor.return_value = [
            _service_package(vendor_id, status="approved", active=True),
            _service_package(vendor_id, status="approved", active=False),
            _service_package(vendor_id, status="waiting_approval", active=False),
            _service_package(vendor_id, status="rejected", active=False),
        ]
        mock_repos["image_repo"].list_by_vendor.return_value = [_portfolio_image(vendor_id)]

        analytics = query_handlers.get_analytics(vendor_id)

        assert analytics["total_inquiries"] == 3
        assert analytics["inquiries_mtd"] == 2
        assert analytics["unresponded_inquiries"] == 2
        assert analytics["read_inquiries"] == 1
        assert analytics["response_rate"] == 33
        assert analytics["active_packages"] == 1
        assert analytics["approved_packages"] == 2
        assert analytics["pending_packages"] == 1
        assert analytics["rejected_packages"] == 1
        assert analytics["portfolio_count"] == 1
        assert analytics["avg_response_time_hours"] is None
        assert analytics["conversion_rate"] is None
        assert "total_views" in analytics["unavailable_metrics"]
