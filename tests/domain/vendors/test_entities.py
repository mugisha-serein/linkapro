from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from freezegun import freeze_time

from domain.shared.utils import utc_now
from domain.vendors.entities import (
    Inquiry,
    PortfolioImage,
    PortfolioQualityStatus,
    PortfolioVisibilityStatus,
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
        "cloudinary_public_id": "vendor/portfolio/image",
        "cloudinary_secure_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
        "caption": "Reception setup",
        "order": 0,
        "media_type": "image",
        "upload_status": "uploaded",
        "quality_status": "passed",
        "visibility_status": "approved",
        "mime_type": "image/jpeg",
        "file_size": 1024,
        "width": 1200,
        "height": 800,
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

    def test_lifecycle_timestamps_must_be_persistently_ordered(self):
        now = utc_now()
        with pytest.raises(VendorProfileValidationError) as exc_info:
            valid_profile(
                status=VendorStatus.APPROVED,
                created_at=now,
                submitted_at=now - timedelta(days=1),
                approved_at=now,
                updated_at=now,
            )

        assert "submitted_at" in exc_info.value.field_errors

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
            created_at=utc_now() - timedelta(days=2),
            updated_at=utc_now(),
            submitted_at=utc_now() - timedelta(days=1),
            rejection_reason="Incomplete",
            rejected_at=utc_now(),
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

    def test_approve_and_reject_pending_profile(self):
        frozen = datetime(2025, 1, 1, tzinfo=utc_now().tzinfo)

        with freeze_time(frozen):
            profile = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=utc_now())
            profile.approve()

        assert profile.status == VendorStatus.APPROVED
        assert profile.approved_at == frozen

        with freeze_time(frozen):
            rejected = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=utc_now())
            rejected.reject("Insufficient portfolio")

        assert rejected.status == VendorStatus.REJECTED
        assert rejected.rejected_at == frozen
        assert rejected.rejection_reason == "Insufficient portfolio"

    def test_blank_rejection_reason_rejected_and_atomic(self):
        now = utc_now()
        profile = valid_profile(status=VendorStatus.PENDING_REVIEW, submitted_at=now, updated_at=now)
        original = profile.__dict__.copy()

        with pytest.raises(VendorProfileValidationError) as exc_info:
            profile.reject(" ")

        assert "rejection_reason" in exc_info.value.field_errors
        assert profile.__dict__ == original

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

    def test_only_rwf_currency_is_supported_until_currency_policy_exists(self):
        with pytest.raises(PackageValidationError) as exc_info:
            valid_package(currency="USD")

        assert "currency" in exc_info.value.field_errors

    def test_update_details_is_atomic_when_candidate_invalid(self):
        package = valid_package(name="Original", price=Decimal("1000.00"))
        original = package.__dict__.copy()

        with pytest.raises(PackageValidationError):
            package.update_details(name="Updated", price=Decimal("10.123"))

        assert package.__dict__ == original

    def test_update_details_respects_approved_package_cooldown(self):
        now = utc_now()
        package = valid_package(
            approval_status="approved",
            is_active=True,
            last_approved_at=now,
        )

        with pytest.raises(Exception):
            package.update_details(name="Updated package")

    def test_update_details_resets_approved_package_after_cooldown(self):
        now = utc_now()
        package = valid_package(
            approval_status="approved",
            is_active=True,
            last_approved_at=now - timedelta(days=16),
        )

        package.update_details(name="Updated package")

        assert package.name == "Updated package"
        assert package.approval_status == "waiting_approval"
        assert package.is_active is False
        assert package.next_vendor_edit_allowed_at is not None

    def test_deleted_rejected_and_unapproved_package_cannot_activate(self):
        for package in [
            valid_package(is_deleted=True, is_active=False),
            valid_package(approval_status="waiting_approval", is_active=False),
            valid_package(approval_status="rejected", is_active=False),
        ]:
            with pytest.raises(InvalidPackageTransition):
                package.activate()


class TestPortfolioImage:
    def test_negative_order_rejected(self):
        with pytest.raises(PortfolioValidationError) as exc_info:
            valid_portfolio(order=-1)

        assert "order" in exc_info.value.field_errors

    def test_mime_type_must_match_media_type(self):
        with pytest.raises(PortfolioValidationError) as exc_info:
            valid_portfolio(media_type="image", mime_type="video/mp4")

        assert "mime_type" in exc_info.value.field_errors

    def test_mark_uploaded_keeps_quality_pending_until_quality_review(self):
        image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())
        image.mark_queued()
        image.mark_processing()

        image.mark_uploaded(public_id="asset", secure_url="https://example.com/image.jpg")

        assert image.upload_status == "uploaded"
        assert image.quality_status == PortfolioQualityStatus.PENDING_ANALYSIS.value

        image.mark_quality_passed()
        assert image.quality_status == PortfolioQualityStatus.PASSED.value

    def test_approved_asset_and_caption_changes_return_to_private_or_review(self):
        image = valid_portfolio()

        image.attach_cloudinary_asset(public_id="new-asset", secure_url="https://example.com/new.jpg")

        assert image.visibility_status == PortfolioVisibilityStatus.PRIVATE.value
        assert image.quality_status == PortfolioQualityStatus.PENDING_ANALYSIS.value

        reviewed = valid_portfolio()
        reviewed.update_caption("New caption")
        assert reviewed.visibility_status == PortfolioVisibilityStatus.WAITING_APPROVAL.value

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

    def test_historical_inquiry_remains_valid_after_event_date_passes(self):
        inquiry = valid_inquiry(event_date=(utc_now() - timedelta(days=365)).date())

        inquiry.mark_read()
        inquiry.mark_read()

        assert inquiry.is_read is True

    def test_new_inquiry_rejects_event_date_outside_creation_window(self):
        with pytest.raises(InquiryValidationError) as exc_info:
            Inquiry.create(
                vendor_id=uuid.uuid4(),
                client_name="Planner",
                client_email="planner@example.com",
                message="Can you support my event?",
                event_date=(utc_now() - timedelta(days=30)).date(),
            )

        assert "event_date" in exc_info.value.field_errors

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
