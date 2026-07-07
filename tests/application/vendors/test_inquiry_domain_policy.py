import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest

from application.vendors.commands import SendInquiryCommand
from application.vendors.handlers import VendorCommandHandlers
from domain.shared.utils import utc_now
from domain.vendors.entities import ServiceCategory, VendorProfile, VendorStatus
from domain.vendors.inquiry_policy import VendorInquiryPolicyError


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


def _profile(status):
    now = utc_now()
    rejection_fields = {}
    lifecycle_fields = {}
    if status == VendorStatus.PENDING_REVIEW:
        lifecycle_fields["created_at"] = now - timedelta(days=1)
        lifecycle_fields["updated_at"] = now
        lifecycle_fields["submitted_at"] = now
    if status in {VendorStatus.APPROVED, VendorStatus.SUSPENDED}:
        lifecycle_fields["created_at"] = now - timedelta(days=2)
        lifecycle_fields["updated_at"] = now
        lifecycle_fields["submitted_at"] = now - timedelta(days=1)
        lifecycle_fields["approved_at"] = now
    if status == VendorStatus.REJECTED:
        lifecycle_fields["created_at"] = now - timedelta(days=2)
        lifecycle_fields["updated_at"] = now
        lifecycle_fields["submitted_at"] = now - timedelta(days=1)
        lifecycle_fields["rejected_at"] = now
        rejection_fields["rejection_reason"] = "Policy issue"
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        business_name="Vendor",
        category=ServiceCategory.CATERING,
        description="Food service with complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        status=status,
        **lifecycle_fields,
        **rejection_fields,
    )


def _send_inquiry_command(vendor_id):
    return SendInquiryCommand(
        vendor_id=vendor_id,
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you help with my event?",
    )


def test_send_inquiry_rejects_missing_vendor(handlers, mock_repos):
    vendor_id = uuid.uuid4()
    mock_repos["vendor_repo"].get_by_id.return_value = None

    with pytest.raises(VendorInquiryPolicyError, match="Vendor not found"):
        handlers.send_inquiry(_send_inquiry_command(vendor_id))

    mock_repos["inquiry_repo"].save.assert_not_called()
    mock_repos["event_dispatcher"].dispatch.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [
        VendorStatus.DRAFT,
        VendorStatus.PENDING_REVIEW,
        VendorStatus.REJECTED,
        VendorStatus.SUSPENDED,
    ],
)
def test_send_inquiry_rejects_unapproved_vendor(status, handlers, mock_repos):
    profile = _profile(status)
    mock_repos["vendor_repo"].get_by_id.return_value = profile

    with pytest.raises(VendorInquiryPolicyError, match="not available"):
        handlers.send_inquiry(_send_inquiry_command(profile.id))

    mock_repos["inquiry_repo"].save.assert_not_called()
    mock_repos["event_dispatcher"].dispatch.assert_not_called()


def test_send_inquiry_allows_approved_vendor(handlers, mock_repos):
    profile = _profile(VendorStatus.APPROVED)
    mock_repos["vendor_repo"].get_by_id.return_value = profile
    mock_repos["inquiry_repo"].save.side_effect = lambda inquiry: inquiry

    result = handlers.send_inquiry(_send_inquiry_command(profile.id))

    assert result.vendor_id == profile.id
    mock_repos["inquiry_repo"].save.assert_called_once()
    mock_repos["event_dispatcher"].dispatch.assert_called_once()
