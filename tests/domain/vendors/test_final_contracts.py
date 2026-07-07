from datetime import datetime, timedelta
from decimal import Decimal
import uuid

import pytest

from domain.shared.utils import utc_now
from domain.vendors import (
    Inquiry,
    InquiryReceived,
    InvalidPackageTransition,
    InvalidPortfolioTransition,
    InvalidVendorTransition,
    MediaAsset,
    Page,
    PageRequest,
    PackageValidationError,
    PortfolioImage,
    PortfolioMediaDeactivated,
    PortfolioValidationError,
    ServiceCategory,
    ServicePackage,
    ServicePackageCreated,
    ServicePackageUpdated,
    VendorProfile,
    VendorProfileValidationError,
    VendorSubmittedForReview,
)
from domain.vendors.interfaces import IPortfolioImageRepository, IServicePackageRepository
from domain.vendors.package_edit_policy import mark_vendor_package_public_edit


def profile_data(**overrides):
    data = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "business_name": "Kigali Events",
        "category": ServiceCategory.PHOTOGRAPHY,
        "description": "Professional event coverage across Kigali.",
        "service_area": "Kigali",
        "contact_email": "vendor@example.com",
        "contact_phone": "+250788123456",
    }
    data.update(overrides)
    return data


def package_data(**overrides):
    data = {
        "id": uuid.uuid4(),
        "vendor_id": uuid.uuid4(),
        "name": "Standard package",
        "description": "Clear event package",
        "price": Decimal("1000.00"),
        "currency": "RWF",
        "package_tier": "standard",
    }
    data.update(overrides)
    return data


def portfolio_data(**overrides):
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
    return data


def test_vendor_rehydrate_requires_persisted_lifecycle_timestamps():
    with pytest.raises(VendorProfileValidationError) as exc_info:
        VendorProfile.rehydrate(**profile_data(status="approved"))

    assert "approved_at" in exc_info.value.field_errors


def test_vendor_custom_category_only_allowed_for_other_category():
    with pytest.raises(VendorProfileValidationError) as exc_info:
        VendorProfile(**profile_data(custom_category="Lighting"))

    assert "custom_category" in exc_info.value.field_errors

    profile = VendorProfile(**profile_data(category="other", custom_category="Lighting"))
    assert profile.category == ServiceCategory.OTHER
    assert profile.custom_category == "Lighting"


def test_vendor_transition_records_event_only_after_success():
    profile = VendorProfile(**profile_data())

    with pytest.raises(InvalidVendorTransition):
        profile.reject("Invalid order")
    assert profile.pull_events() == []

    profile.submit_for_review()
    events = profile.pull_events()

    assert len(events) == 1
    assert isinstance(events[0], VendorSubmittedForReview)
    assert profile.pull_events() == []


def test_service_package_create_defaults_to_inactive_and_records_event():
    package = ServicePackage.create(
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="Clear event package",
        price=Decimal("1000.00"),
    )

    assert package.is_active is False
    assert package.approval_status == "waiting_approval"
    assert isinstance(package.pull_events()[0], ServicePackageCreated)


def test_service_package_rehydrate_requires_approved_timestamp():
    with pytest.raises(PackageValidationError) as exc_info:
        ServicePackage.rehydrate(**package_data(approval_status="approved"))

    assert "last_approved_at" in exc_info.value.field_errors


def test_service_package_noop_update_preserves_version_timestamp_and_events():
    updated_at = utc_now()
    package = ServicePackage(**package_data(updated_at=updated_at, version=2))
    package.pull_events()

    package.update_details(
        name=" Standard package ",
        description=" Clear event package ",
        price=Decimal("1000.00"),
        currency="rwf",
        package_tier="Standard",
    )

    assert package.version == 2
    assert package.updated_at == updated_at
    assert package.pull_events() == []


def test_approved_or_rejected_package_public_change_returns_to_waiting_inactive():
    approved = ServicePackage(
        **package_data(
            approval_status="approved",
            is_active=True,
            last_approved_at=utc_now() - timedelta(days=20),
        )
    )

    approved.update_details(description="Updated clear event package")

    assert approved.approval_status == "waiting_approval"
    assert approved.is_active is False
    assert isinstance(approved.pull_events()[0], ServicePackageUpdated)

    rejected = ServicePackage(
        **package_data(
            approval_status="rejected",
            rejection_reason="Needs more detail",
            is_active=False,
        )
    )

    rejected.update_details(name="Updated package")

    assert rejected.approval_status == "waiting_approval"
    assert rejected.rejection_reason is None
    assert rejected.is_active is False


def test_deleted_package_rejects_later_activation():
    package = ServicePackage(
        **package_data(
            approval_status="approved",
            last_approved_at=utc_now(),
            is_active=True,
        )
    )

    package.deactivate()

    with pytest.raises(InvalidPackageTransition):
        package.activate()


def test_pure_package_edit_policy_returns_markers_without_mutating_package():
    now = utc_now()
    package = ServicePackage(
        **package_data(
            approval_status="approved",
            last_approved_at=now - timedelta(days=20),
            is_active=True,
        )
    )
    original = package.__dict__.copy()

    markers = mark_vendor_package_public_edit(package, now=now, public_fields_changed=True)

    assert markers["approval_status"] == "waiting_approval"
    assert markers["is_active"] is False
    assert package.__dict__ == original


def test_media_asset_rejects_private_hosts_and_requires_pair():
    with pytest.raises(PortfolioValidationError):
        MediaAsset(public_id="asset", secure_url="https://localhost/image.jpg")

    asset = MediaAsset(public_id="asset", secure_url="https://example.com/image.jpg")
    assert asset.public_id == "asset"


def test_portfolio_defaults_and_deleted_media_are_closed_to_mutation():
    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())

    assert image.upload_status == "staged"
    assert image.quality_status == "pending_analysis"
    assert image.visibility_status == "private"

    image.deactivate()
    assert isinstance(image.pull_events()[0], PortfolioMediaDeactivated)

    with pytest.raises(InvalidPortfolioTransition):
        image.update_caption("New caption")


def test_portfolio_mark_uploaded_requires_valid_remote_asset():
    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())

    with pytest.raises(PortfolioValidationError):
        image.mark_uploaded()

    image.mark_uploaded(public_id="asset", secure_url="https://example.com/image.jpg")
    assert image.upload_status == "uploaded"
    assert image.secure_url == "https://example.com/image.jpg"


def test_portfolio_metadata_requires_strict_primitives_and_cloudinary_pair_match():
    with pytest.raises(PortfolioValidationError) as exc_info:
        PortfolioImage(**portfolio_data(is_active="true", width=True))

    assert {"is_active", "width"} <= set(exc_info.value.field_errors)

    with pytest.raises(PortfolioValidationError) as mismatch:
        PortfolioImage(**portfolio_data(cloudinary_public_id="different"))

    assert "cloudinary_public_id" in mismatch.value.field_errors


def test_inquiry_event_date_is_date_only_with_bounds_and_events():
    with pytest.raises(Exception):
        Inquiry(
            id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            event_date=datetime.now(),
        )

    inquiry = Inquiry.create(
        vendor_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support my event?",
        event_date=(utc_now() + timedelta(days=30)).date(),
    )
    assert isinstance(inquiry.pull_events()[0], InquiryReceived)


def test_pagination_and_repository_contracts_are_ownership_scoped():
    page = Page(items=[1], total=1, limit=1, offset=0, next_cursor="next")

    assert page.items == [1]
    assert page.next_cursor == "next"
    assert PageRequest(limit=100, offset=10_000).limit == 100

    with pytest.raises(ValueError):
        PageRequest(limit=101)
    with pytest.raises(ValueError):
        PageRequest(offset=10_001)

    assert "get_for_vendor" in IServicePackageRepository.__abstractmethods__
    assert "delete_for_vendor" in IServicePackageRepository.__abstractmethods__
    assert "get_for_vendor" in IPortfolioImageRepository.__abstractmethods__
    assert "delete_for_vendor" in IPortfolioImageRepository.__abstractmethods__
