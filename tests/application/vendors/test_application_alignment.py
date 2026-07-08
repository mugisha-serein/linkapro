from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import ast
import uuid

import pytest

from application.vendors.commands import (
    ActivateServicePackageCommand,
    AddPortfolioImageCommand,
    ApproveVendorCommand,
    AuthenticatedActor,
    CreateServicePackageCommand,
    CreateVendorProfileCommand,
    DeactivateServicePackageCommand,
    DeletePortfolioImageCommand,
    MarkInquiryReadCommand,
    ModeratorActor,
    ReorderPortfolioImagesCommand,
    ReinstateVendorCommand,
    RejectVendorCommand,
    ResourceVersion,
    SendInquiryCommand,
    SubmitVendorForReviewCommand,
    SuspendVendorCommand,
    UpdateServicePackageCommand,
    UpdateVendorProfileCommand,
)
from application.vendors.dtos import PageDTO, PortfolioImageDTO, ServicePackageDTO
from application.vendors.errors import InvalidVendorCommand, VendorConflict, VendorOperationForbidden, VendorResourceNotFound
from application.vendors.handlers import VendorCommandHandlers, VendorQueryHandlers
from application.vendors.queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    GetVendorQuery,
    ListInquiriesQuery,
    ListPortfolioImagesQuery,
    ListRecentVendorActivityQuery,
    ListServicePackagesQuery,
)
from domain.shared.utils import utc_now
from domain.vendors.entities import (
    Inquiry,
    PackageApprovalStatus,
    PortfolioImage,
    ServiceCategory,
    ServicePackage,
    VendorProfile,
    VendorStatus,
)
from domain.vendors.events import (
    InquiryReceived,
    PortfolioMediaReordered,
    ServicePackageCreated,
    VendorApproved,
    VendorProfileUpdated,
)
from domain.vendors.interfaces import Page, PageRequest


def _actor(user_id: uuid.UUID | None = None) -> AuthenticatedActor:
    return AuthenticatedActor(user_id=user_id or uuid.uuid4())


def _moderator(user_id: uuid.UUID | None = None) -> ModeratorActor:
    return ModeratorActor(user_id=user_id or uuid.uuid4())


def _profile(*, status=VendorStatus.DRAFT, version=0) -> VendorProfile:
    now = utc_now()
    kwargs = {}
    if status == VendorStatus.PENDING_REVIEW:
        kwargs.update(created_at=now, updated_at=now, submitted_at=now)
    if status == VendorStatus.APPROVED:
        kwargs.update(created_at=now, updated_at=now, submitted_at=now, approved_at=now)
    if status == VendorStatus.REJECTED:
        kwargs.update(
            created_at=now,
            updated_at=now,
            submitted_at=now,
            rejected_at=now,
            rejection_reason="Needs more complete verification details.",
        )
    if status == VendorStatus.SUSPENDED:
        kwargs.update(created_at=now, updated_at=now, submitted_at=now, approved_at=now)
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        business_name="Vendor",
        category=ServiceCategory.CATERING,
        description="Reliable vendor services for complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        status=status,
        version=version,
        **kwargs,
    )


def _package(vendor_id: uuid.UUID, *, version=0, status="waiting_approval", active=False) -> ServicePackage:
    kwargs = {}
    if status == PackageApprovalStatus.APPROVED.value:
        kwargs["last_approved_at"] = utc_now() - timedelta(days=20)
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Standard package",
        description="Clear standard event package with defined deliverables.",
        price=Decimal("5000.00"),
        currency="RWF",
        package_tier="standard",
        approval_status=status,
        is_active=active,
        version=version,
        **kwargs,
    )


def _image(vendor_id: uuid.UUID, *, order=0, version=0) -> PortfolioImage:
    return PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        public_id=f"asset-{order}",
        secure_url="https://example.com/image.jpg",
        caption=f"Image {order}",
        order=order,
        version=version,
    )


def _inquiry(vendor_id: uuid.UUID, *, version=0) -> Inquiry:
    return Inquiry(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support my event?",
        event_date=date.today() + timedelta(days=30),
        version=version,
    )


class EventDispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, event):
        self.events.append(event)


class VendorRepo:
    def __init__(self, profiles=()):
        self.profiles = {profile.id: profile for profile in profiles}
        self.add_calls = []
        self.save_calls = []
        self.get_by_id_calls = []
        self.fail_on_save = False

    def add(self, profile):
        self.add_calls.append(profile)
        self.profiles[profile.id] = profile
        return profile

    def save(self, profile, *, expected_version):
        self.save_calls.append((profile, expected_version))
        if self.fail_on_save:
            raise RuntimeError("persistence failed")
        self.profiles[profile.id] = profile
        return profile

    def get_by_id(self, vendor_id):
        self.get_by_id_calls.append(vendor_id)
        return self.profiles.get(vendor_id)

    def get_by_user_id(self, user_id):
        return next((profile for profile in self.profiles.values() if profile.user_id == user_id), None)

    def list_by_status(self, status, page):
        items = [profile for profile in self.profiles.values() if profile.status == status]
        return Page(items=items[: page.limit], total=len(items), limit=page.limit, offset=page.offset)


class ImageRepo:
    def __init__(self, images=()):
        self.images = {image.id: image for image in images}
        self.add_calls = []
        self.save_calls = []
        self.get_for_vendor_calls = []
        self.list_by_vendor_calls = []
        self.allocate_next_order_calls = []

    def add(self, image):
        self.add_calls.append(image)
        self.images[image.id] = image
        return image

    def save(self, image, *, expected_version):
        self.save_calls.append((image, expected_version))
        self.images[image.id] = image
        return image

    def get_for_vendor(self, vendor_id, image_id):
        self.get_for_vendor_calls.append((vendor_id, image_id))
        image = self.images.get(image_id)
        return image if image and image.vendor_id == vendor_id else None

    def list_by_vendor(self, vendor_id, page):
        self.list_by_vendor_calls.append((vendor_id, page))
        items = [image for image in self.images.values() if image.vendor_id == vendor_id]
        return Page(items=items[: page.limit], total=len(items), limit=page.limit, offset=page.offset)

    def allocate_next_order(self, vendor_id):
        self.allocate_next_order_calls.append(vendor_id)
        return len([image for image in self.images.values() if image.vendor_id == vendor_id])


class PackageRepo:
    def __init__(self, packages=()):
        self.packages = {package.id: package for package in packages}
        self.add_calls = []
        self.save_calls = []
        self.get_for_vendor_calls = []

    def add(self, package):
        self.add_calls.append(package)
        self.packages[package.id] = package
        return package

    def save(self, package, *, expected_version):
        self.save_calls.append((package, expected_version))
        self.packages[package.id] = package
        return package

    def get_for_vendor(self, vendor_id, package_id):
        self.get_for_vendor_calls.append((vendor_id, package_id))
        package = self.packages.get(package_id)
        return package if package and package.vendor_id == vendor_id else None


class InquiryRepo:
    def __init__(self, inquiries=()):
        self.inquiries = {inquiry.id: inquiry for inquiry in inquiries}
        self.add_calls = []
        self.save_calls = []
        self.get_for_vendor_calls = []
        self.list_by_vendor_calls = []

    def add(self, inquiry):
        self.add_calls.append(inquiry)
        self.inquiries[inquiry.id] = inquiry
        return inquiry

    def save(self, inquiry, *, expected_version):
        self.save_calls.append((inquiry, expected_version))
        self.inquiries[inquiry.id] = inquiry
        return inquiry

    def get_for_vendor(self, vendor_id, inquiry_id):
        self.get_for_vendor_calls.append((vendor_id, inquiry_id))
        inquiry = self.inquiries.get(inquiry_id)
        return inquiry if inquiry and inquiry.vendor_id == vendor_id else None

    def list_by_vendor(self, vendor_id, page):
        self.list_by_vendor_calls.append((vendor_id, page))
        items = [inquiry for inquiry in self.inquiries.values() if inquiry.vendor_id == vendor_id]
        return Page(items=items[: page.limit], total=len(items), limit=page.limit, offset=page.offset)


class ReadPort:
    def __init__(self):
        self.package_page = PageDTO(items=(), total=0, limit=50, offset=0)
        self.summary = {"planner_requests": 1}
        self.analytics_payload = {"total_inquiries": 2}
        self.activity = PageDTO(items=({"type": "inquiry_received"},), total=1, limit=10, offset=0)
        self.calls = []

    def list_service_packages(self, vendor_id, page):
        self.calls.append(("packages", vendor_id, page))
        return self.package_page

    def dashboard_summary(self, vendor_id):
        self.calls.append(("summary", vendor_id))
        return self.summary

    def analytics(self, vendor_id):
        self.calls.append(("analytics", vendor_id))
        return self.analytics_payload

    def recent_activity(self, vendor_id, page):
        self.calls.append(("activity", vendor_id, page))
        return self.activity


class IdempotencyPort:
    def __init__(self):
        self.records = {}
        self.executions = []

    def execute_once(self, *, scope, actor_id, key, payload_fingerprint, operation):
        record_key = (scope, actor_id, key)
        existing = self.records.get(record_key)
        if existing is not None:
            existing_fingerprint, result = existing
            if existing_fingerprint != payload_fingerprint:
                raise VendorConflict("Idempotency key was already used with a different payload.")
            return result
        result = operation()
        self.executions.append((scope, actor_id, key, payload_fingerprint, result))
        self.records[record_key] = (payload_fingerprint, result)
        return result


class AuthorizationPort:
    def __init__(self, denied_vendor_ids=()):
        self.denied_vendor_ids = set(denied_vendor_ids)
        self.calls = []

    def assert_actor_owns_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))
        if vendor_id in self.denied_vendor_ids:
            raise VendorOperationForbidden("Actor does not own this vendor.")

    def assert_actor_can_access_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))
        if vendor_id in self.denied_vendor_ids:
            raise VendorOperationForbidden("Actor cannot access this vendor.")

    def assert_moderator_can_moderate_vendor(self, moderator, vendor_id):
        self.calls.append((moderator, vendor_id))
        if vendor_id in self.denied_vendor_ids:
            raise VendorOperationForbidden("Moderator cannot moderate this vendor.")


class ReorderUow:
    def __init__(self, images):
        self.images = tuple(images)
        self.persist_calls = []
        self.list_calls = []
        self.fail = False

    def list_vendor_images(self, vendor_id, page):
        self.list_calls.append((vendor_id, page))
        items = [image for image in self.images if image.vendor_id == vendor_id]
        return Page(items=items, total=len(items), limit=page.limit, offset=page.offset)

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        self.persist_calls.append((vendor_id, tuple(images), expected_versions))
        if self.fail:
            raise RuntimeError("transaction failed")
        return tuple(images)


def _handlers(*, vendor_repo=None, image_repo=None, package_repo=None, inquiry_repo=None, dispatcher=None, **kwargs):
    kwargs.setdefault("authorization_port", AuthorizationPort())
    return VendorCommandHandlers(
        vendor_repo=vendor_repo or VendorRepo(),
        image_repo=image_repo or ImageRepo(),
        package_repo=package_repo or PackageRepo(),
        inquiry_repo=inquiry_repo or InquiryRepo(),
        event_dispatcher=dispatcher or EventDispatcher(),
        **kwargs,
    )


def test_creation_uses_add_not_save_and_idempotency_replays_result():
    idem = IdempotencyPort()
    vendor_repo = VendorRepo()
    handler = _handlers(vendor_repo=vendor_repo, idempotency_port=idem)
    actor = _actor()
    cmd = CreateVendorProfileCommand(
        actor=actor,
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key="create-profile-1",
    )

    first = handler.create_profile(cmd)
    second = handler.create_profile(cmd)

    assert first is second
    assert len(vendor_repo.add_calls) == 1
    assert vendor_repo.save_calls == []


def test_idempotency_payload_conflict_raises_vendor_conflict():
    idem = IdempotencyPort()
    actor = _actor()
    profile = _profile(status=VendorStatus.APPROVED)
    vendor_repo = VendorRepo([profile])
    handler = _handlers(vendor_repo=vendor_repo, idempotency_port=idem)
    base = CreateServicePackageCommand(
        actor=actor,
        vendor_id=profile.id,
        name="Standard",
        description="Clear package details for a full event.",
        price=Decimal("5000"),
        idempotency_key="pkg-key",
    )
    changed = CreateServicePackageCommand(
        actor=actor,
        vendor_id=base.vendor_id,
        name="Different",
        description="Clear package details for a full event.",
        price=Decimal("5000"),
        idempotency_key="pkg-key",
    )

    handler.create_service_package(base)

    with pytest.raises(VendorConflict):
        handler.create_service_package(changed)


def test_vendor_owned_commands_require_authenticated_actor_context():
    vendor_owned_commands = (
        CreateVendorProfileCommand,
        UpdateVendorProfileCommand,
        SubmitVendorForReviewCommand,
        AddPortfolioImageCommand,
        DeletePortfolioImageCommand,
        ReorderPortfolioImagesCommand,
        CreateServicePackageCommand,
        UpdateServicePackageCommand,
        DeactivateServicePackageCommand,
        ActivateServicePackageCommand,
        MarkInquiryReadCommand,
    )

    for command_type in vendor_owned_commands:
        assert "actor" in command_type.__dataclass_fields__

    with pytest.raises(InvalidVendorCommand):
        UpdateVendorProfileCommand(actor=uuid.uuid4(), vendor_id=uuid.uuid4(), expected_version=1)


def test_vendor_moderation_commands_require_moderator_actor_context():
    moderation_commands = (
        ApproveVendorCommand,
        RejectVendorCommand,
        SuspendVendorCommand,
        ReinstateVendorCommand,
    )

    for command_type in moderation_commands:
        assert "moderator" in command_type.__dataclass_fields__

    with pytest.raises(InvalidVendorCommand):
        ApproveVendorCommand(moderator=uuid.uuid4(), vendor_id=uuid.uuid4(), expected_version=1)


def test_moderation_authorization_denial_happens_before_vendor_loads_or_transitions():
    vendor_id = uuid.uuid4()
    moderator = _moderator()
    profile = _profile(status=VendorStatus.PENDING_REVIEW, version=1)
    profile.id = vendor_id
    repo = VendorRepo([profile])
    auth = AuthorizationPort(denied_vendor_ids={vendor_id})
    handler = _handlers(vendor_repo=repo, authorization_port=auth)

    with pytest.raises(VendorOperationForbidden):
        handler.approve_vendor(ApproveVendorCommand(moderator=moderator, vendor_id=vendor_id, expected_version=1))
    with pytest.raises(VendorOperationForbidden):
        handler.reject_vendor(
            RejectVendorCommand(moderator=moderator, vendor_id=vendor_id, expected_version=1, reason="Incomplete")
        )
    with pytest.raises(VendorOperationForbidden):
        handler.suspend_vendor(
            SuspendVendorCommand(moderator=moderator, vendor_id=vendor_id, expected_version=1, reason="Policy")
        )
    with pytest.raises(VendorOperationForbidden):
        handler.reinstate_vendor(ReinstateVendorCommand(moderator=moderator, vendor_id=vendor_id, expected_version=1))

    assert repo.get_by_id_calls == []
    assert repo.save_calls == []
    assert profile.status == VendorStatus.PENDING_REVIEW
    assert auth.calls == [(moderator, vendor_id)] * 4


def test_authorization_denial_happens_before_vendor_owned_aggregate_loads_or_writes():
    vendor_id = uuid.uuid4()
    actor = _actor()
    profile = _profile(version=1)
    profile.id = vendor_id
    image = _image(vendor_id, version=1)
    package = _package(vendor_id, version=1)
    inquiry = _inquiry(vendor_id, version=1)
    vendor_repo = VendorRepo([profile])
    image_repo = ImageRepo([image])
    package_repo = PackageRepo([package])
    inquiry_repo = InquiryRepo([inquiry])
    uow = ReorderUow([image])
    auth = AuthorizationPort(denied_vendor_ids={vendor_id})
    handler = _handlers(
        vendor_repo=vendor_repo,
        image_repo=image_repo,
        package_repo=package_repo,
        inquiry_repo=inquiry_repo,
        reorder_uow=uow,
        authorization_port=auth,
    )

    with pytest.raises(VendorOperationForbidden):
        handler.update_profile(
            UpdateVendorProfileCommand(actor=actor, vendor_id=vendor_id, expected_version=1, business_name="Blocked")
        )
    with pytest.raises(VendorOperationForbidden):
        handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=actor,
                vendor_id=vendor_id,
                public_id="asset",
                secure_url="https://example.com/a.jpg",
            )
        )
    with pytest.raises(VendorOperationForbidden):
        handler.delete_portfolio_image(
            DeletePortfolioImageCommand(actor=actor, vendor_id=vendor_id, image_id=image.id, expected_version=1)
        )
    with pytest.raises(VendorOperationForbidden):
        handler.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(
                actor=actor,
                vendor_id=vendor_id,
                image_ids_in_order=(image.id,),
                expected_versions=(ResourceVersion(image.id, 1),),
            )
        )
    with pytest.raises(VendorOperationForbidden):
        handler.create_service_package(
            CreateServicePackageCommand(
                actor=actor,
                vendor_id=vendor_id,
                name="Blocked",
                description="Blocked package details for this event.",
                price=Decimal("5000"),
            )
        )
    with pytest.raises(VendorOperationForbidden):
        handler.update_service_package(
            UpdateServicePackageCommand(actor=actor, vendor_id=vendor_id, package_id=package.id, expected_version=1)
        )
    with pytest.raises(VendorOperationForbidden):
        handler.mark_inquiry_read(
            MarkInquiryReadCommand(actor=actor, vendor_id=vendor_id, inquiry_id=inquiry.id, expected_version=1)
        )

    assert vendor_repo.get_by_id_calls == []
    assert image_repo.get_for_vendor_calls == []
    assert image_repo.add_calls == []
    assert package_repo.get_for_vendor_calls == []
    assert package_repo.add_calls == []
    assert inquiry_repo.get_for_vendor_calls == []
    assert uow.list_calls == []
    assert len(auth.calls) == 7


def test_add_portfolio_media_loads_vendor_and_returns_stable_missing_vendor_error_before_allocation():
    vendor_id = uuid.uuid4()
    vendor_repo = VendorRepo()
    image_repo = ImageRepo()
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=vendor_repo, image_repo=image_repo, dispatcher=dispatcher)

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                public_id="asset",
                secure_url="https://example.com/image.jpg",
            )
        )

    assert exc_info.value.code == "vendor_not_found"
    assert vendor_repo.get_by_id_calls == [vendor_id]
    assert image_repo.allocate_next_order_calls == []
    assert image_repo.add_calls == []
    assert dispatcher.events == []


def test_add_portfolio_media_policy_forbids_suspended_vendor_before_order_allocation():
    profile = _profile(status=VendorStatus.SUSPENDED)
    vendor_repo = VendorRepo([profile])
    image_repo = ImageRepo()
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=vendor_repo, image_repo=image_repo, dispatcher=dispatcher)

    with pytest.raises(VendorOperationForbidden) as exc_info:
        handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=profile.id,
                public_id="asset",
                secure_url="https://example.com/image.jpg",
            )
        )

    assert exc_info.value.code == "vendor_portfolio_media_creation_forbidden"
    assert vendor_repo.get_by_id_calls == [profile.id]
    assert image_repo.allocate_next_order_calls == []
    assert image_repo.add_calls == []
    assert dispatcher.events == []


def test_add_portfolio_media_allowed_statuses_keep_existing_order_allocation_path():
    allowed_statuses = (
        VendorStatus.DRAFT,
        VendorStatus.PENDING_REVIEW,
        VendorStatus.APPROVED,
        VendorStatus.REJECTED,
    )

    for status in allowed_statuses:
        profile = _profile(status=status)
        existing = _image(profile.id, order=0)
        vendor_repo = VendorRepo([profile])
        image_repo = ImageRepo([existing])
        handler = _handlers(vendor_repo=vendor_repo, image_repo=image_repo)

        result = handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=profile.id,
                public_id="asset-new",
                secure_url="https://example.com/new-image.jpg",
            )
        )

        assert result.order == 1
        assert vendor_repo.get_by_id_calls == [profile.id]
        assert image_repo.allocate_next_order_calls == [profile.id]
        assert len(image_repo.add_calls) == 1


def test_expected_version_is_required_and_stale_commands_fail_before_mutation():
    profile = _profile(version=4)
    repo = VendorRepo([profile])
    handler = _handlers(vendor_repo=repo)

    with pytest.raises(InvalidVendorCommand):
        UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=True, business_name="Bad")

    with pytest.raises(VendorConflict):
        handler.update_profile(
            UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=3, business_name="New")
        )

    assert profile.business_name == "Vendor"
    assert repo.save_calls == []


def test_profile_update_uses_domain_transition_saves_expected_version_and_dispatches_domain_event():
    profile = _profile(version=2)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher)

    result = handler.update_profile(
        UpdateVendorProfileCommand(
            actor=_actor(),
            vendor_id=profile.id,
            expected_version=2,
            business_name="Updated Vendor",
            contact_email="UPDATED@EXAMPLE.COM",
        )
    )

    assert result.business_name == "Updated Vendor"
    assert result.contact_email == "updated@example.com"
    assert result.version == 3
    assert repo.save_calls == [(profile, 2)]
    assert len(dispatcher.events) == 1
    assert isinstance(dispatcher.events[0], VendorProfileUpdated)
    assert dispatcher.events[0].aggregate_version == 3


def test_noop_update_does_not_save_or_dispatch():
    profile = _profile(version=2)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher)

    result = handler.update_profile(
        UpdateVendorProfileCommand(
            actor=_actor(),
            vendor_id=profile.id,
            expected_version=2,
            business_name=" Vendor ",
            contact_email="VENDOR@EXAMPLE.COM",
        )
    )

    assert result.version == 2
    assert repo.save_calls == []
    assert dispatcher.events == []


def test_failed_persistence_dispatches_no_events():
    profile = _profile(version=1)
    repo = VendorRepo([profile])
    repo.fail_on_save = True
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher)

    with pytest.raises(RuntimeError):
        handler.update_profile(
            UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=1, business_name="New")
        )

    assert dispatcher.events == []


def test_profile_validation_failure_is_atomic():
    profile = _profile(version=1)
    original = profile.__dict__.copy()
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()

    with pytest.raises(Exception):
        _handlers(vendor_repo=repo, dispatcher=dispatcher).update_profile(
            UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=1, contact_email="not-email")
        )

    assert profile.__dict__ == original
    assert repo.save_calls == []
    assert dispatcher.events == []


def test_lifecycle_events_are_pulled_from_aggregate_after_save():
    profile = _profile(status=VendorStatus.PENDING_REVIEW, version=7)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher)

    result = handler.approve_vendor(
        ApproveVendorCommand(moderator=_moderator(), vendor_id=profile.id, expected_version=7)
    )

    assert result.status == VendorStatus.APPROVED.value
    assert repo.save_calls == [(profile, 7)]
    assert len(dispatcher.events) == 1
    assert isinstance(dispatcher.events[0], VendorApproved)
    assert dispatcher.events[0].event_id
    assert profile.pull_events() == []


def test_service_package_update_uses_owned_lookup_and_single_domain_path():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=5)
    repo = PackageRepo([package])
    dispatcher = EventDispatcher()
    handler = _handlers(package_repo=repo, dispatcher=dispatcher)

    result = handler.update_service_package(
        UpdateServicePackageCommand(
            actor=_actor(),
            vendor_id=vendor_id,
            package_id=package.id,
            expected_version=5,
            description="Updated clear package details for a full event.",
        )
    )

    assert result.version == 6
    assert repo.save_calls == [(package, 5)]

    with pytest.raises(VendorResourceNotFound):
        handler.update_service_package(
            UpdateServicePackageCommand(
                actor=_actor(),
                vendor_id=uuid.uuid4(),
                package_id=package.id,
                expected_version=6,
                name="Foreign",
            )
        )


def test_create_service_package_and_inquiry_use_factories_add_and_domain_events():
    vendor_id = uuid.uuid4()
    profile = _profile(status=VendorStatus.APPROVED)
    profile.id = vendor_id
    vendor_repo = VendorRepo([profile])
    package_repo = PackageRepo()
    inquiry_repo = InquiryRepo()
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=vendor_repo, package_repo=package_repo, inquiry_repo=inquiry_repo, dispatcher=dispatcher)

    package_result = handler.create_service_package(
        CreateServicePackageCommand(
            actor=_actor(),
            vendor_id=vendor_id,
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
        )
    )
    inquiry_result = handler.send_inquiry(
        SendInquiryCommand(
            vendor_id=vendor_id,
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            event_date=date.today() + timedelta(days=40),
        )
    )

    assert package_result.is_active is False
    assert len(package_repo.add_calls) == 1
    assert len(inquiry_repo.add_calls) == 1
    assert inquiry_result.event_date == date.today() + timedelta(days=40)
    assert [type(event) for event in dispatcher.events] == [ServicePackageCreated, InquiryReceived]


def test_create_service_package_loads_vendor_and_returns_stable_missing_vendor_error():
    vendor_id = uuid.uuid4()
    vendor_repo = VendorRepo()
    package_repo = PackageRepo()
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=vendor_repo, package_repo=package_repo, dispatcher=dispatcher)

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.create_service_package(
            CreateServicePackageCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                name="Standard",
                description="Clear package details for a full event.",
                price=Decimal("5000"),
            )
        )

    assert exc_info.value.code == "vendor_not_found"
    assert vendor_repo.get_by_id_calls == [vendor_id]
    assert package_repo.add_calls == []
    assert dispatcher.events == []


def test_create_service_package_policy_forbids_unapproved_vendor_statuses_before_package_creation():
    forbidden_statuses = (
        VendorStatus.DRAFT,
        VendorStatus.PENDING_REVIEW,
        VendorStatus.REJECTED,
        VendorStatus.SUSPENDED,
    )

    for status in forbidden_statuses:
        profile = _profile(status=status)
        vendor_repo = VendorRepo([profile])
        package_repo = PackageRepo()
        dispatcher = EventDispatcher()
        handler = _handlers(vendor_repo=vendor_repo, package_repo=package_repo, dispatcher=dispatcher)

        with pytest.raises(VendorOperationForbidden) as exc_info:
            handler.create_service_package(
                CreateServicePackageCommand(
                    actor=_actor(),
                    vendor_id=profile.id,
                    name="Standard",
                    description="Clear package details for a full event.",
                    price=Decimal("5000"),
                )
            )

        assert exc_info.value.code == "vendor_service_package_creation_forbidden"
        assert vendor_repo.get_by_id_calls == [profile.id]
        assert package_repo.add_calls == []
        assert dispatcher.events == []


def test_inquiry_command_rejects_datetime_event_date():
    with pytest.raises(InvalidVendorCommand):
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            event_date=datetime.now(),
        )


def test_delete_and_activate_vendor_owned_commands_require_vendor_id_and_versions():
    vendor_id = uuid.uuid4()
    image = _image(vendor_id, version=1)
    image_repo = ImageRepo([image])
    package = _package(vendor_id, version=2, status="approved", active=False)
    package_repo = PackageRepo([package])
    dispatcher = EventDispatcher()
    handler = _handlers(image_repo=image_repo, package_repo=package_repo, dispatcher=dispatcher)

    with pytest.raises(InvalidVendorCommand):
        DeletePortfolioImageCommand(actor=_actor(), vendor_id=None, image_id=image.id, expected_version=1)

    handler.delete_portfolio_image(
        DeletePortfolioImageCommand(actor=_actor(), vendor_id=vendor_id, image_id=image.id, expected_version=1)
    )
    handler.activate_package(
        ActivateServicePackageCommand(actor=_actor(), vendor_id=vendor_id, package_id=package.id, expected_version=2)
    )

    assert image_repo.save_calls[0][1] == 1
    assert package_repo.save_calls[0][1] == 2


def test_reorder_uses_unit_of_work_and_dispatches_after_success():
    vendor_id = uuid.uuid4()
    first = _image(vendor_id, order=0, version=1)
    second = _image(vendor_id, order=1, version=2)
    uow = ReorderUow([first, second])
    dispatcher = EventDispatcher()
    handler = _handlers(dispatcher=dispatcher, reorder_uow=uow)

    result = handler.reorder_portfolio_images(
        ReorderPortfolioImagesCommand(
            actor=_actor(),
            vendor_id=vendor_id,
            image_ids_in_order=(second.id, first.id),
            expected_versions=(
                ResourceVersion(second.id, 2),
                ResourceVersion(first.id, 1),
            ),
        )
    )

    assert [item.id for item in result.items] == [second.id, first.id]
    assert len(uow.persist_calls) == 1
    assert [type(event) for event in dispatcher.events] == [PortfolioMediaReordered, PortfolioMediaReordered]


def test_reorder_failure_dispatches_no_events():
    vendor_id = uuid.uuid4()
    first = _image(vendor_id, order=0, version=1)
    second = _image(vendor_id, order=1, version=2)
    uow = ReorderUow([first, second])
    uow.fail = True
    dispatcher = EventDispatcher()
    handler = _handlers(dispatcher=dispatcher, reorder_uow=uow)

    with pytest.raises(RuntimeError):
        handler.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                image_ids_in_order=(second.id, first.id),
                expected_versions=(ResourceVersion(second.id, 2), ResourceVersion(first.id, 1)),
            )
        )

    assert dispatcher.events == []


def test_reorder_rejects_duplicate_missing_or_foreign_ids_before_persisting():
    vendor_id = uuid.uuid4()
    first = _image(vendor_id, order=0, version=1)
    uow = ReorderUow([first])
    handler = _handlers(reorder_uow=uow)

    with pytest.raises(InvalidVendorCommand):
        handler.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                image_ids_in_order=(first.id, first.id),
                expected_versions=(ResourceVersion(first.id, 1),),
            )
        )
    with pytest.raises(VendorResourceNotFound):
        handler.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                image_ids_in_order=(uuid.uuid4(),),
                expected_versions=(ResourceVersion(first.id, 1),),
            )
        )

    assert uow.persist_calls == []


def test_page_results_are_mapped_to_page_dto_and_read_port_is_mandatory():
    vendor_id = uuid.uuid4()
    profile = _profile(status=VendorStatus.PENDING_REVIEW)
    profile.id = vendor_id
    image = _image(vendor_id)
    inquiry = _inquiry(vendor_id)
    read_port = ReadPort()
    auth = AuthorizationPort()
    actor = _actor()
    package_dto = ServicePackageDTO(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Package",
        description="Description",
        price=Decimal("1"),
        currency="RWF",
        package_tier="standard",
        approval_status="waiting_approval",
        rejection_reason=None,
        is_active=False,
        is_deleted=False,
        deleted_at=None,
        version=0,
    )
    read_port.package_page = PageDTO(items=(package_dto,), total=1, limit=5, offset=0)

    with pytest.raises(InvalidVendorCommand):
        VendorQueryHandlers(VendorRepo(), ImageRepo(), InquiryRepo(), None, auth)
    unauthenticated_query = VendorQueryHandlers(VendorRepo([profile]), ImageRepo([image]), InquiryRepo([inquiry]), read_port)

    assert unauthenticated_query.get_vendor_by_user(profile.user_id).id == profile.id
    with pytest.raises(InvalidVendorCommand) as exc_info:
        unauthenticated_query.get_vendor(GetVendorQuery(actor=actor, vendor_id=vendor_id))
    assert exc_info.value.field_errors == {"authorization_port": ["Vendor authorization is required."]}

    query = VendorQueryHandlers(VendorRepo([profile]), ImageRepo([image]), InquiryRepo([inquiry]), read_port, auth)

    assert query.list_pending_approvals(PageRequest(limit=5)).items[0].id == profile.id
    assert query.get_vendor(GetVendorQuery(actor=actor, vendor_id=vendor_id)).id == vendor_id
    assert (
        query.list_portfolio_images(
            ListPortfolioImagesQuery(actor=actor, vendor_id=vendor_id, page=PageRequest(limit=5))
        ).items[0].id
        == image.id
    )
    assert (
        query.list_inquiries(ListInquiriesQuery(actor=actor, vendor_id=vendor_id, page=PageRequest(limit=5))).items[0].id
        == inquiry.id
    )
    assert (
        query.list_service_packages(
            ListServicePackagesQuery(actor=actor, vendor_id=vendor_id, page=PageRequest(limit=5))
        ).items
        == (package_dto,)
    )
    assert query.get_dashboard_summary(GetVendorDashboardSummaryQuery(actor=actor, vendor_id=vendor_id)) == read_port.summary
    assert query.get_analytics(GetVendorAnalyticsQuery(actor=actor, vendor_id=vendor_id)) == read_port.analytics_payload
    assert (
        query.get_recent_activity(ListRecentVendorActivityQuery(actor=actor, vendor_id=vendor_id)).items
        == read_port.activity.items
    )


def test_private_vendor_queries_authorize_before_repository_or_read_port_calls():
    vendor_id = uuid.uuid4()
    actor = _actor()
    profile = _profile()
    profile.id = vendor_id
    image = _image(vendor_id)
    inquiry = _inquiry(vendor_id)
    vendor_repo = VendorRepo([profile])
    image_repo = ImageRepo([image])
    inquiry_repo = InquiryRepo([inquiry])
    read_port = ReadPort()
    auth = AuthorizationPort(denied_vendor_ids={vendor_id})
    query = VendorQueryHandlers(vendor_repo, image_repo, inquiry_repo, read_port, auth)

    with pytest.raises(VendorOperationForbidden):
        query.get_vendor(GetVendorQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.list_portfolio_images(ListPortfolioImagesQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.list_inquiries(ListInquiriesQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.list_service_packages(ListServicePackagesQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.get_dashboard_summary(GetVendorDashboardSummaryQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.get_analytics(GetVendorAnalyticsQuery(actor=actor, vendor_id=vendor_id))
    with pytest.raises(VendorOperationForbidden):
        query.get_recent_activity(ListRecentVendorActivityQuery(actor=actor, vendor_id=vendor_id))

    assert vendor_repo.get_by_id_calls == []
    assert image_repo.list_by_vendor_calls == []
    assert inquiry_repo.list_by_vendor_calls == []
    assert read_port.calls == []
    assert auth.calls == [(actor, vendor_id)] * 7


def test_portfolio_image_dto_has_no_unsafe_lifecycle_defaults():
    with pytest.raises(TypeError):
        PortfolioImageDTO(id=uuid.uuid4(), vendor_id=uuid.uuid4(), secure_url="", caption=None, order=0)


def test_cooldown_compatibility_alias_is_removed():
    assert not Path("application/vendors/cooldown_handlers.py").exists()


def test_application_vendor_source_has_no_forbidden_imports_private_domain_calls_or_manual_events():
    root = Path("application/vendors")
    forbidden_import_roots = {"django", "django_app", "rest_framework", "infrastructure", "sqlalchemy", "celery", "tasks"}
    manual_event_names = {
        "VendorProfileUpdated",
        "VendorSubmittedForReview",
        "VendorApproved",
        "VendorRejected",
        "VendorSuspended",
        "VendorReinstated",
        "ServicePackageCreated",
        "ServicePackageUpdated",
        "ServicePackageApproved",
        "ServicePackageRejected",
        "ServicePackageActivated",
        "ServicePackageDeactivated",
        "InquiryReceived",
        "PortfolioMediaReordered",
    }
    protected_attrs = {
        "status",
        "submitted_at",
        "approved_at",
        "rejected_at",
        "rejection_reason",
        "approval_status",
        "is_active",
        "is_deleted",
        "deleted_at",
        "upload_status",
        "quality_status",
        "visibility_status",
        "version",
    }
    offenders = []

    for path in root.rglob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            for name in names:
                if name.split(".", 1)[0] in forbidden_import_roots:
                    offenders.append(f"{path} imports {name}")
            if isinstance(node, ast.Attribute) and node.attr in {"_commit_candidate", "_record", "_bump_version"}:
                offenders.append(f"{path} calls private domain attribute {node.attr}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in manual_event_names:
                offenders.append(f"{path} manually constructs {node.func.id}")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in protected_attrs:
                        offenders.append(f"{path} assigns protected field {target.attr}")

    assert offenders == []
