import uuid
import pytest
from datetime import datetime
from freezegun import freeze_time

from domain.vendors.entities import (
    VendorProfile, VendorStatus, ServiceCategory,
    PortfolioImage, ServicePackage, Inquiry
)
from domain.shared.utils import utc_now


class TestVendorProfile:
    def test_create_draft_profile(self):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test Photography",
            category=ServiceCategory.PHOTOGRAPHY,
            description="We capture moments",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="+250788123456",
        )
        assert profile.status == VendorStatus.DRAFT
        assert profile.submitted_at is None

    def test_submit_for_review_from_draft(self):
<<<<<<< HEAD
=======
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test Photography",
            category=ServiceCategory.PHOTOGRAPHY,
            description="We capture moments",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="+250788123456",
        )
>>>>>>> 028240308e063a7dfd4d77eb2f2a606995767bc4
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            profile = valid_profile()
            profile.submit_for_review()
        assert profile.status == VendorStatus.PENDING_REVIEW
        assert profile.submitted_at == frozen

    def test_submit_for_review_from_rejected(self):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.REJECTED,
            rejection_reason="Incomplete",
        )
        profile.submit_for_review()
        assert profile.status == VendorStatus.PENDING_REVIEW

    def test_cannot_submit_from_approved(self):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="Cannot submit from status"):
            profile.submit_for_review()

    def test_approve_pending_profile(self):
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
        frozen = datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            profile.approve()
        assert profile.status == VendorStatus.APPROVED
        assert profile.approved_at == frozen

    def test_cannot_approve_non_pending(self):
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
        with pytest.raises(ValueError, match="Only pending"):
            profile.approve()

    def test_reject_pending_profile(self):
<<<<<<< HEAD
=======
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
>>>>>>> 028240308e063a7dfd4d77eb2f2a606995767bc4
        frozen = datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)
        with freeze_time(frozen):
            profile = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=utc_now())
            profile.reject("Insufficient portfolio")
        assert profile.status == VendorStatus.REJECTED
        assert profile.rejected_at == frozen
        assert profile.rejection_reason == "Insufficient portfolio"

    def test_suspend_approved_vendor(self):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.APPROVED,
        )
        profile.suspend()
        assert profile.status == VendorStatus.SUSPENDED

    def test_cannot_suspend_non_approved(self):
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
        with pytest.raises(ValueError, match="Only approved"):
            profile.suspend()

    def test_reinstate_suspended_vendor(self):
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            business_name="Test",
            category=ServiceCategory.CATERING,
            description="Food",
            service_area="Kigali",
            contact_email="test@example.com",
            contact_phone="123",
            status=VendorStatus.SUSPENDED,
        )
        profile.reinstate()
        assert profile.status == VendorStatus.APPROVED


class TestPortfolioImage:
    def test_update_caption(self):
        img = PortfolioImage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
<<<<<<< HEAD
            client_name=" Planner ",
            client_email="PLANNER@EXAMPLE.COM",
            client_phone="+250 788 000 000",
            message="Please share availability.",
            event_date=(utc_now() + timedelta(days=30)).date(),
=======
            public_id="abc",
            secure_url="https://...",
            caption="Old",
>>>>>>> 028240308e063a7dfd4d77eb2f2a606995767bc4
        )
        img.update_caption("New caption")
        assert img.caption == "New caption"

    def test_reorder(self):
        img = PortfolioImage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            public_id="abc",
            secure_url="https://...",
            order=2,
        )
        img.reorder(5)
        assert img.order == 5


class TestServicePackage:
    def test_update_details(self):
        pkg = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Basic",
            description="desc",
            price=1000.0,
        )
        with freeze_time("2025-01-01"):
            pkg.update_details(name="Premium", price=2000.0)
        assert pkg.name == "Premium"
        assert pkg.price == 2000.0
        assert pkg.updated_at == datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)

    def test_deactivate_and_activate(self):
        pkg = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            name="Basic",
            description="desc",
            price=1000.0,
            is_active=True,
        )
        pkg.deactivate()
        assert pkg.is_active is False
        pkg.activate()
        assert pkg.is_active is True