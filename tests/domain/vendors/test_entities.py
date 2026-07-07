from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from freezegun import freeze_time

from domain.shared.utils import utc_now
from domain.vendors.entities import (
    Inquiry,
    PortfolioImage,
    ServiceCategory,
    ServicePackage,
    VendorProfile,
    VendorStatus,
)
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


class TestVendorProfile:
    def test_create_draft_profile(self):
        profile = VendorProfile.create_draft(
            user_id=uuid.uuid4(),
            business_name=" Test Photography ",
            category="photography",
            description="We capture elegant wedding and event moments.",
            service_area="Kigali",
            contact_email="TEST@EXAMPLE.COM",
            contact_phone="+250 788 123 456",
        )

        assert profile.status == VendorStatus.DRAFT
        assert profile.contact_email == "test@example.com"
        assert profile.contact_phone == "+250788123456"
        assert profile.submitted_at is None

    def test_invalid_email_phone_and_url_are_rejected(self):
        with pytest.raises(VendorProfileValidationError) as exc_info:
            valid_profile(
                contact_email="bad-email",
                contact_phone="not a phone",
                website="javascript:alert(1)",
            )

        assert exc_info.value.code == "vendor_profile_invalid"
        assert set(exc_info.value.field_errors) >= {"contact_email", "contact_phone", "website"}

    def test_blank_oversized_and_control_character_fields_rejected(self):
        with pytest.raises(VendorProfileValidationError) as exc_info:
            valid_profile(business_name=" ", service_area="Kigali\x00", description="x" * 5001)

        assert "business_name" in exc_info.value.field_errors
        assert "service_area" in exc_info.value.field_errors
        assert "description" in exc_info.value.field_errors

    def test_raw_invalid_status_rejected(self):
        with pytest.raises(VendorProfileValidationError) as exc_info:
            valid_profile(status="published")

        assert exc_info.value.field_errors["status"] == ["Choose a valid status."]

    def test_submit_for_review_from_draft(self):
        frozen = datetime(2025, 1, 1, 12, 0, 0, tzinfo=utc_now().tzinfo)

        with freeze_time(frozen):
            profile = valid_profile()
            profile.submit_for_review()

        assert profile.status == VendorStatus.PENDING_REVIEW
        assert profile.submitted_at == frozen
        assert profile.updated_at == frozen

    def test_rejected_resubmission_clears_old_rejection_metadata(self):
        profile = valid_profile(
            status=VendorStatus.REJECTED,
            rejection_reason="Incomplete",
            rejected_at=utc_now() - timedelta(days=1),
        )

        profile.submit_for_review()

        assert profile.status == VendorStatus.PENDING_REVIEW
        assert profile.rejection_reason is None
        assert profile.rejected_at is None

    def test_cannot_submit_from_approved_leaves_object_unchanged(self):
        profile = valid_profile(status=VendorStatus.APPROVED)
        original = profile.__dict__.copy()

        with pytest.raises(InvalidVendorTransition):
            profile.submit_for_review()

        assert profile.__dict__ == original

    def test_approve_clears_rejection_metadata(self):
        profile = valid_profile(
            status=VendorStatus.PENDING_REVIEW,
            submitted_at=utc_now(),
            rejection_reason=None,
        )

        profile.approve()

        assert profile.status == VendorStatus.APPROVED
        assert profile.rejected_at is None
        assert profile.rejection_reason is None
        assert profile.approved_at is not None

    def test_blank_rejection_reason_rejected_and_atomic(self):
        profile = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=utc_now())
        original = profile.__dict__.copy()

        with pytest.raises(VendorProfileValidationError) as exc_info:
            profile.reject(" ")

        assert "rejection_reason" in exc_info.value.field_errors
        assert profile.__dict__ == original

    def test_reject_pending_profile(self):
        frozen = datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)

        with freeze_time(frozen):
            profile = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=utc_now())
            profile.reject("Insufficient portfolio")

        assert profile.status == VendorStatus.REJECTED
        assert profile.rejected_at == frozen
        assert profile.rejection_reason == "Insufficient portfolio"

    def test_suspend_and_reinstate_vendor(self):
        profile = valid_profile(status=VendorStatus.APPROVED)

        profile.suspend("Policy review")
        assert profile.status == VendorStatus.SUSPENDED

        profile.reinstate()
        assert profile.status == VendorStatus.APPROVED


class TestServicePackage:
    def test_invalid_money_values_are_rejected(self):
        for value in [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("0")]:
            with pytest.raises(PackageValidationError):
                valid_package(price=value)

    def test_excessive_scale_and_too_large_price_rejected(self):
        with pytest.raises(PackageValidationError) as scale_error:
            valid_package(price=Decimal("10.123"))
        with pytest.raises(PackageValidationError) as max_error:
            valid_package(price=Decimal("10000000000.00"))

        assert "price" in scale_error.value.field_errors
        assert "price" in max_error.value.field_errors

    def test_invalid_currency_tier_and_status_rejected(self):
        with pytest.raises(PackageValidationError) as exc_info:
            valid_package(currency="BTC", package_tier="diamond", approval_status="live")

        assert set(exc_info.value.field_errors) >= {"currency", "package_tier", "approval_status"}

    def test_update_details_is_atomic_when_candidate_invalid(self):
        package = valid_package(name="Original", price=Decimal("1000.00"))
        original = package.__dict__.copy()

        with pytest.raises(PackageValidationError):
            package.update_details(name="Updated", price=Decimal("10.123"))

        assert package.__dict__ == original

    def test_update_details_resets_approved_package_to_waiting_approval(self):
        package = valid_package(approval_status="approved", is_active=True)

        package.update_details(name="Updated package", price=Decimal("2000.00"))

        assert package.name == "Updated package"
        assert package.price == Decimal("2000.00")
        assert package.approval_status == "waiting_approval"
        assert package.is_active is False

    def test_deleted_rejected_and_unapproved_package_cannot_activate(self):
        for package in [
            valid_package(is_deleted=True, is_active=False),
            valid_package(approval_status="waiting_approval", is_active=False),
            valid_package(approval_status="rejected", is_active=False),
        ]:
            with pytest.raises(InvalidPackageTransition):
                package.activate()

    def test_approved_package_can_activate_and_deactivate_is_idempotent(self):
        package = valid_package(approval_status="approved", is_active=False)

        package.activate()
        assert package.is_active is True

        package.deactivate()
        first_deleted_at = package.deleted_at
        package.deactivate()
        assert package.is_active is False
        assert package.is_deleted is True
        assert package.deleted_at == first_deleted_at


class TestPortfolioImage:
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
            vendor_id=uuid.uuid4(),
            client_name=" Planner ",
            client_email="PLANNER@EXAMPLE.COM",
            client_phone="+250 788 000 000",
            message="Please share availability.",
            event_date=(utc_now() + timedelta(days=30)).date(),
        )

        assert inquiry.client_name == "Planner"
        assert inquiry.client_email == "planner@example.com"
        assert inquiry.client_phone == "+250788000000"
        assert inquiry.is_read is False

        inquiry.mark_read()
        inquiry.mark_read()
        assert inquiry.is_read is True
