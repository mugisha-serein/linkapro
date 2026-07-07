import uuid
import pytest
from datetime import datetime
from freezegun import freeze_time

from domain.vendors.entities import (
    VendorProfile, VendorStatus, ServiceCategory,
    PortfolioImage, ServicePackage, Inquiry
)
<<<<<<< HEAD
from domain.vendors.errors import (
    InquiryValidationError,
    InvalidPackageTransition,
    InvalidPortfolioTransition,
    InvalidVendorTransition,
    PackageValidationError,
    PortfolioValidationError,
    VendorProfileValidationError,
)


def valid_profile(**overrides):
    now = utc_now()
    data = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "business_name": "Test Photography",
        "category": ServiceCategory.PHOTOGRAPHY,
        "description": "We capture elegant wedding and event moments.",
        "service_area": "Kigali",
        "contact_email": "test@example.com",
        "contact_phone": "+250788123456",
    }
    data.update(overrides)
    status = data.get("status")
    if status == VendorStatus.PENDING_REVIEW and data.get("submitted_at") is None:
        data.update({"created_at": now, "updated_at": now, "submitted_at": now})
    if status == VendorStatus.APPROVED and data.get("approved_at") is None:
        data.update({"created_at": now, "updated_at": now, "submitted_at": now, "approved_at": now})
    if status == VendorStatus.SUSPENDED and data.get("approved_at") is None:
        data.update({"created_at": now, "updated_at": now, "submitted_at": now, "approved_at": now})
    return VendorProfile(**data)


def valid_package(**overrides):
    data = {
        "id": uuid.uuid4(),
        "vendor_id": uuid.uuid4(),
        "name": "Standard package",
        "description": "Clear standard event package with defined deliverables.",
        "price": Decimal("1000.00"),
        "currency": "RWF",
        "package_tier": "standard",
        "approval_status": "waiting_approval",
        "is_active": False,
    }
    data.update(overrides)
    if data.get("approval_status") == "approved" and data.get("last_approved_at") is None:
        data["last_approved_at"] = utc_now()
    if data.get("approval_status") == "rejected" and not data.get("rejection_reason"):
        data["rejection_reason"] = "Needs more detail"
    if data.get("is_deleted") is True and data.get("deleted_at") is None:
        data["deleted_at"] = utc_now()
    return ServicePackage(**data)


def valid_portfolio(**overrides):
    data = {
        "id": uuid.uuid4(),
        "vendor_id": uuid.uuid4(),
        "public_id": "vendor/portfolio/image",
        "secure_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
        "caption": "Reception setup",
        "order": 0,
        "media_type": "image",
        "upload_status": "uploaded",
        "quality_status": "passed",
        "visibility_status": "approved",
    }
    data.update(overrides)
    return PortfolioImage(**data)


def valid_inquiry(**overrides):
    data = {
        "id": uuid.uuid4(),
        "vendor_id": uuid.uuid4(),
        "client_name": "Planner One",
        "client_email": "planner@example.com",
        "message": "Can you support my event?",
    }
    data.update(overrides)
    return Inquiry(**data)
=======
from domain.shared.utils import utc_now
>>>>>>> origin/main


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
<<<<<<< HEAD
            submitted_at=utc_now(),
            rejection_reason=None,
=======
>>>>>>> origin/main
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
<<<<<<< HEAD
    def test_negative_order_rejected(self):
        with pytest.raises(PortfolioValidationError) as exc_info:
            valid_portfolio(order=-1)

        assert "order" in exc_info.value.field_errors

    def test_invalid_caption_rejected(self):
        with pytest.raises(PortfolioValidationError) as exc_info:
            valid_portfolio(caption="Bad\x00caption")

        assert "caption" in exc_info.value.field_errors

    def test_impossible_approved_state_rejected(self):
        with pytest.raises(PortfolioValidationError) as exc_info:
            valid_portfolio(upload_status="queued", visibility_status="approved")

        assert "visibility_status" in exc_info.value.field_errors

    def test_approved_media_requires_safe_url_uploaded_passed_active_state(self):
        with pytest.raises(PortfolioValidationError):
            valid_portfolio(secure_url="http://example.com/image.jpg")
        with pytest.raises(PortfolioValidationError):
            valid_portfolio(quality_status="failed")
        with pytest.raises(PortfolioValidationError):
            valid_portfolio(is_active=False)

    def test_failed_upload_becomes_private(self):
        image = valid_portfolio(
            upload_status="processing",
            quality_status="pending_analysis",
            visibility_status="private",
        )

        image.mark_failed("Virus scan failed")

        assert image.upload_status == "failed"
        assert image.quality_status == "failed"
        assert image.visibility_status == "private"
        assert image.failure_reason == "Virus scan failed"

    def test_deactivate_is_idempotent(self):
        image = valid_portfolio()

        image.deactivate()
        first_deleted_at = image.deleted_at
        image.deactivate()

        assert image.is_active is False
        assert image.is_deleted is True
        assert image.visibility_status == "private"
        assert image.deleted_at == first_deleted_at

    def test_failed_mutation_leaves_object_unchanged(self):
        image = valid_portfolio()
        original = image.__dict__.copy()

        with pytest.raises(PortfolioValidationError):
            image.update_caption("x" * 501)

        assert image.__dict__ == original

    def test_submit_and_approve_portfolio(self):
        image = valid_portfolio(visibility_status="private")

        image.submit_for_approval()
        assert image.visibility_status == "waiting_approval"

        image.approve()
        assert image.visibility_status == "approved"

    def test_cannot_approve_non_waiting_portfolio(self):
        image = valid_portfolio(visibility_status="private")

        with pytest.raises(InvalidPortfolioTransition):
            image.approve()


class TestInquiry:
    def test_invalid_email_rejected(self):
        with pytest.raises(InquiryValidationError) as exc_info:
            valid_inquiry(client_email="bad")

        assert "client_email" in exc_info.value.field_errors

    def test_blank_and_oversized_message_rejected(self):
        with pytest.raises(InquiryValidationError) as blank:
            valid_inquiry(message=" ")
        with pytest.raises(InquiryValidationError) as oversized:
            valid_inquiry(message="x" * 5001)

        assert "message" in blank.value.field_errors
        assert "message" in oversized.value.field_errors

    def test_invalid_phone_and_date_rejected(self):
        with pytest.raises(InquiryValidationError) as exc_info:
            valid_inquiry(client_phone="not phone", event_date=datetime(2025, 1, 1))

        assert set(exc_info.value.field_errors) >= {"client_phone", "event_date"}

    def test_valid_inquiry_succeeds_and_mark_read_is_idempotent(self):
        inquiry = Inquiry.create(
=======
    def test_update_caption(self):
        img = PortfolioImage(
            id=uuid.uuid4(),
>>>>>>> origin/main
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