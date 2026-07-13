from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import inspect
from pathlib import Path
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
    ProtectedStateMutationError,
    ServiceCategory,
    ServicePackage,
    ServicePackageActivated,
    ServicePackageApproved,
    ServicePackageCreated,
    ServicePackageUpdated,
    VendorApproved,
    VendorProfile,
    VendorProfileValidationError,
    VendorSubmittedForReview,
)
from domain.vendors.interfaces import (
    IInquiryRepository,
    IPortfolioImageRepository,
    IServicePackageRepository,
    IVendorProfileRepository,
)
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
        "description": "Clear standard event package with defined deliverables.",
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
    assert isinstance(events[0].event_id, uuid.UUID)
    assert events[0].aggregate_id == profile.id
    assert events[0].aggregate_version == 1
    assert events[0].occurred_at.tzinfo is not None
    assert profile.pull_events() == []


def test_consecutive_vendor_events_are_preserved_until_pulled():
    profile = VendorProfile(**profile_data())

    profile.submit_for_review()
    profile.approve()

    events = profile.pull_events()
    assert [type(event) for event in events] == [VendorSubmittedForReview, VendorApproved]
    assert [event.aggregate_version for event in events] == [1, 2]
    assert events[0].event_id != events[1].event_id
    assert profile.pull_events() == []


def test_service_package_create_defaults_to_inactive_and_records_event():
    package = ServicePackage.create(
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="Clear standard event package with defined deliverables.",
        price=Decimal("1000.00"),
    )

    assert package.is_active is False
    assert package.approval_status == "waiting_approval"
    event = package.pull_events()[0]
    assert isinstance(event, ServicePackageCreated)
    assert event.aggregate_id == package.id
    assert event.aggregate_version == 0


def test_failed_package_mutation_preserves_pending_events_and_state():
    package = ServicePackage.create(
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="Clear standard event package with defined deliverables.",
        price=Decimal("1000.00"),
    )
    original = {key: value for key, value in package.__dict__.items() if key != "_events"}
    pending_events = list(package._events)

    with pytest.raises(PackageValidationError):
        package.update_details(price=Decimal("10.123"))

    assert {key: value for key, value in package.__dict__.items() if key != "_events"} == original
    assert package._events == pending_events


def test_consecutive_package_events_are_preserved_until_pulled():
    package = ServicePackage.create(
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="Clear standard event package with defined deliverables.",
        price=Decimal("1000.00"),
    )

    package.approve()
    package.activate()

    events = package.pull_events()
    assert [type(event) for event in events] == [
        ServicePackageCreated,
        ServicePackageApproved,
        ServicePackageActivated,
    ]
    assert [event.aggregate_version for event in events] == [0, 1, 2]


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
        description=" Clear standard event package with defined deliverables. ",
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

    approved.update_details(description="Updated clear standard event package with defined deliverables.")

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

    with pytest.raises(InvalidPackageTransition):
        package.update_details(name="Changed package")


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
    with pytest.raises(TypeError):
        markers["is_active"] = True
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


def test_invalid_portfolio_state_transitions_are_rejected():
    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())

    with pytest.raises(InvalidPortfolioTransition):
        image.mark_uploaded(public_id="asset", secure_url="https://example.com/image.jpg")

    with pytest.raises(InvalidPortfolioTransition):
        image.reject("Not waiting")

    image.mark_queued()
    with pytest.raises(InvalidPortfolioTransition):
        image.mark_queued()


def test_portfolio_mark_uploaded_requires_valid_remote_asset():
    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())
    image.mark_queued()
    image.mark_processing()

    with pytest.raises(PortfolioValidationError):
        image.mark_uploaded()

    image.mark_uploaded(public_id="asset", secure_url="https://example.com/image.jpg")
    assert image.upload_status == "uploaded"
    assert image.quality_status == "pending_analysis"
    assert image.secure_url == "https://example.com/image.jpg"

    image.mark_quality_passed()
    assert image.quality_status == "passed"


def test_portfolio_metadata_requires_strict_primitives_and_cloudinary_pair_match():
    with pytest.raises(PortfolioValidationError) as exc_info:
        PortfolioImage(**portfolio_data(is_active="true", width=True))

    assert {"is_active", "width"} <= set(exc_info.value.field_errors)

    with pytest.raises(PortfolioValidationError) as mismatch:
        PortfolioImage(**portfolio_data(cloudinary_public_id="different"))

    assert "cloudinary_public_id" in mismatch.value.field_errors


def test_portfolio_deleted_rehydration_requires_deleted_timestamp():
    with pytest.raises(PortfolioValidationError) as exc_info:
        PortfolioImage(**portfolio_data(is_deleted=True, is_active=False, visibility_status="private"))

    assert "deleted_at" in exc_info.value.field_errors


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
    assert PageRequest(limit=5, cursor="  next-page  ").cursor == "next-page"

    with pytest.raises(ValueError):
        PageRequest(limit=101)
    with pytest.raises(ValueError):
        PageRequest(offset=10_001)
    with pytest.raises(ValueError):
        PageRequest(limit=True)
    with pytest.raises(ValueError):
        PageRequest(offset=False)
    with pytest.raises(ValueError):
        PageRequest(cursor=" ")
    with pytest.raises(ValueError):
        PageRequest(cursor="x" * 513)
    with pytest.raises(ValueError):
        PageRequest(offset=1, cursor="next")
    with pytest.raises(ValueError):
        Page(items=[1, 2], total=1, limit=10, offset=0)
    with pytest.raises(ValueError):
        Page(items=[1, 2], total=2, limit=1, offset=0)

    assert "get_for_vendor" in IServicePackageRepository.__abstractmethods__
    assert "delete_for_vendor" in IServicePackageRepository.__abstractmethods__
    assert "get_for_vendor" in IPortfolioImageRepository.__abstractmethods__
    assert "delete_for_vendor" in IPortfolioImageRepository.__abstractmethods__


def test_protected_lifecycle_fields_reject_direct_assignment_and_keep_state():
    profile = VendorProfile(**profile_data())
    package = ServicePackage(**package_data())
    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())
    inquiry = Inquiry(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support my event?",
    )

    protected_cases = [
        (profile, "status", "approved"),
        (profile, "submitted_at", utc_now()),
        (profile, "approved_at", utc_now()),
        (profile, "rejected_at", utc_now()),
        (profile, "rejection_reason", "Not enough detail"),
        (profile, "version", 10),
        (package, "approval_status", "approved"),
        (package, "rejection_reason", "Needs detail"),
        (package, "is_active", True),
        (package, "is_deleted", True),
        (package, "deleted_at", utc_now()),
        (package, "version", 10),
        (image, "upload_status", "uploaded"),
        (image, "quality_status", "passed"),
        (image, "visibility_status", "approved"),
        (image, "is_active", False),
        (image, "is_deleted", True),
        (image, "deleted_at", utc_now()),
        (image, "version", 10),
        (inquiry, "is_read", True),
        (inquiry, "version", 10),
    ]

    for aggregate, field_name, attempted_value in protected_cases:
        original_value = getattr(aggregate, field_name)
        with pytest.raises(ProtectedStateMutationError) as exc_info:
            setattr(aggregate, field_name, attempted_value)
        assert exc_info.value.code == "vendor_protected_state_assignment"
        assert getattr(aggregate, field_name) == original_value


def test_replace_and_internal_transitions_still_work_with_protected_state():
    profile = VendorProfile(**profile_data())
    candidate = replace(profile, business_name="Kigali Creative Events")

    assert candidate.business_name == "Kigali Creative Events"

    profile.submit_for_review()
    profile.approve()
    assert profile.status.value == "approved"
    assert profile.version == 2

    package = ServicePackage(**package_data())
    package.approve()
    package.activate()
    assert package.approval_status == "approved"
    assert package.is_active is True
    assert package.version == 2

    image = PortfolioImage(id=uuid.uuid4(), vendor_id=uuid.uuid4())
    image.mark_queued()
    image.mark_processing()
    image.mark_uploaded(public_id="asset", secure_url="https://example.com/image.jpg")
    assert image.upload_status == "uploaded"

    inquiry = Inquiry(
        id=uuid.uuid4(),
        vendor_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support my event?",
    )
    inquiry.mark_read()
    assert inquiry.is_read is True


def test_repository_contracts_separate_add_and_mandatory_expected_version():
    for repository in (
        IVendorProfileRepository,
        IServicePackageRepository,
        IPortfolioImageRepository,
        IInquiryRepository,
    ):
        assert "add" in repository.__abstractmethods__
        save_signature = inspect.signature(repository.save)
        expected_version = save_signature.parameters["expected_version"]
        assert expected_version.kind is inspect.Parameter.KEYWORD_ONLY
        assert expected_version.default is inspect.Signature.empty
        assert expected_version.annotation is int


def test_domain_events_have_identity_metadata_and_ordered_clearing():
    package = ServicePackage.create(
        vendor_id=uuid.uuid4(),
        name="Standard package",
        description="Clear standard event package with defined deliverables.",
        price=Decimal("1000.00"),
    )
    package.approve()
    package.activate()

    events = package.pull_events()

    assert [type(event) for event in events] == [
        ServicePackageCreated,
        ServicePackageApproved,
        ServicePackageActivated,
    ]
    assert [event.aggregate_id for event in events] == [package.id, package.id, package.id]
    assert [event.aggregate_version for event in events] == [0, 1, 2]
    assert len({event.event_id for event in events}) == 3
    assert all(event.occurred_at.tzinfo is not None for event in events)
    assert package.pull_events() == []


def test_vendor_domain_workflow_exists_with_required_commands():
    workflow = Path(__file__).parents[3] / ".github" / "workflows" / "vendor-domain.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "domain/vendors/**" in text
    assert "tests/domain/vendors/**" in text
    assert 'python-version: "3.12"' in text
    assert "python -m compileall domain/vendors" in text
    assert 'python -c "import domain.vendors"' in text
    assert 'python -c "import domain.vendors as v; assert all(hasattr(v, n) for n in v.__all__)"' in text
    assert "python -m pytest tests/domain/vendors -q" in text
    assert "python manage.py check" in text
    assert "git diff --check" in text
