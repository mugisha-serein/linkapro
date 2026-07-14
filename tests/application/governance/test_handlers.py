import uuid
import pytest
from unittest.mock import Mock

from application.governance.commands import (
    ApproveVendorCommand, RejectVendorCommand, SuspendVendorCommand,
    BanUserCommand, SuspendUserCommand, ReinstateUserCommand,
    FlagContentCommand, ResolveFlagCommand, GenerateMetricsCommand
)
from application.governance.handlers import GovernanceCommandHandlers, GovernanceQueryHandlers
from domain.governance.entities import ContentFlag, FlagStatus, ContentType
from domain.vendors.profile.entity import VendorProfile, VendorStatus, ServiceCategory
from domain.identity.entities import User, UserRole, Email


@pytest.fixture
def mock_repos():
    return {
        "audit_repo": Mock(),
        "flag_repo": Mock(),
        "metric_repo": Mock(),
        "vendor_repo": Mock(),
        "user_repo": Mock(),
        "event_dispatcher": Mock(),
    }


@pytest.fixture
def handlers(mock_repos):
    return GovernanceCommandHandlers(
        audit_repo=mock_repos["audit_repo"],
        flag_repo=mock_repos["flag_repo"],
        metric_repo=mock_repos["metric_repo"],
        vendor_repo=mock_repos["vendor_repo"],
        user_repo=mock_repos["user_repo"],
        event_dispatcher=mock_repos["event_dispatcher"],
    )


class TestGovernanceCommandHandlers:
    def test_approve_vendor(self, handlers, mock_repos):
        vendor = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test Vendor",
            category=ServiceCategory.PHOTOGRAPHY,
            description="...",
            service_area="Kigali",
            contact_email="v@t.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
        )
        mock_repos["vendor_repo"].get_by_id.return_value = vendor
        mock_repos["vendor_repo"].save.side_effect = lambda v: v

        cmd = ApproveVendorCommand(admin_id=uuid.uuid4(), vendor_id=vendor.id)
        handlers.approve_vendor(cmd)

        assert vendor.status == VendorStatus.APPROVED
        mock_repos["audit_repo"].save.assert_called_once()
        mock_repos["event_dispatcher"].dispatch.assert_called_once()

    def test_reject_vendor(self, handlers, mock_repos):
        vendor = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test Vendor",
            category=ServiceCategory.CATERING,
            description="...",
            service_area="Kigali",
            contact_email="v@t.com",
            contact_phone="123",
            status=VendorStatus.PENDING_REVIEW,
        )
        mock_repos["vendor_repo"].get_by_id.return_value = vendor
        mock_repos["vendor_repo"].save.side_effect = lambda v: v

        cmd = RejectVendorCommand(admin_id=uuid.uuid4(), vendor_id=vendor.id, reason="Incomplete")
        handlers.reject_vendor(cmd)

        assert vendor.status == VendorStatus.REJECTED
        assert vendor.rejection_reason == "Incomplete"
        mock_repos["audit_repo"].save.assert_called_once()

    def test_ban_user(self, handlers, mock_repos):
        user = User(
            id=uuid.uuid4(),
            email=Email("u@t.com"),
            password_hash=None,
            first_name="U",
            last_name="Ser",
            role=UserRole.PLANNER,
            is_active=True,
        )
        mock_repos["user_repo"].get_by_id.return_value = user
        mock_repos["user_repo"].save.side_effect = lambda u: u

        cmd = BanUserCommand(admin_id=uuid.uuid4(), user_id=user.id)
        handlers.ban_user(cmd)

        assert user.is_active is False
        mock_repos["audit_repo"].save.assert_called_once()

    def test_flag_content(self, handlers, mock_repos):
        mock_repos["flag_repo"].save.side_effect = lambda f: f

        cmd = FlagContentCommand(
            reported_by=uuid.uuid4(),
            content_type="vendor_profile",
            content_id=uuid.uuid4(),
            reason="Misleading info"
        )
        result = handlers.flag_content(cmd)

        assert result.content_type == "vendor_profile"
        assert result.status == "pending"
        mock_repos["flag_repo"].save.assert_called_once()

    def test_resolve_flag_reviewed(self, handlers, mock_repos):
        flag = ContentFlag(
            id=uuid.uuid4(),
            reported_by=uuid.uuid4(),
            content_type=ContentType.REVIEW,
            content_id=uuid.uuid4(),
            reason="Spam",
        )
        mock_repos["flag_repo"].get_by_id.return_value = flag
        mock_repos["flag_repo"].save.side_effect = lambda f: f

        cmd = ResolveFlagCommand(admin_id=uuid.uuid4(), flag_id=flag.id, notes="Removed", dismiss=False)
        result = handlers.resolve_flag(cmd)

        assert result.status == "reviewed"
        assert result.admin_notes == "Removed"
        mock_repos["audit_repo"].save.assert_called_once()

    def test_generate_metrics(self, handlers, mock_repos):
        metric = Mock()
        mock_repos["metric_repo"].generate_current_metrics.return_value = metric
        mock_repos["metric_repo"].save.return_value = metric

        cmd = GenerateMetricsCommand()
        result = handlers.generate_metrics(cmd)

        assert result is not None
        mock_repos["metric_repo"].generate_current_metrics.assert_called_once()
        mock_repos["metric_repo"].save.assert_called_once()
