from __future__ import annotations

from dataclasses import MISSING, fields
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import ast
import inspect
import uuid
from typing import get_args, get_origin, get_type_hints

import pytest

from application.vendors.inquiries.commands import MarkInquiryReadCommand, SendInquiryCommand
from application.vendors.packages.commands import ActivateServicePackageCommand, CreateServicePackageCommand, DeactivateServicePackageCommand, UpdateServicePackageCommand
from application.vendors.portfolio.commands import AddPortfolioImageCommand, DeletePortfolioImageCommand, ReorderPortfolioImagesCommand
from application.vendors.profile.commands import ApproveVendorCommand, CreateVendorProfileCommand, ReinstateVendorCommand, RejectVendorCommand, SubmitVendorForReviewCommand, SuspendVendorCommand, UpdateVendorProfileCommand
from application.vendors.shared.commands import AuthenticatedActor, ModeratorActor, ResourceVersion
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.shared.dtos import PageDTO
from application.vendors.errors import (
    DuplicateVendorProfile,
    InvalidVendorCommand,
    InvalidVendorCommand,
    VendorApplicationConfigurationError,
    VendorConflict,
    VendorOperationForbidden,
    VendorResourceNotFound,
)
from application.vendors.shared import ports as vendor_ports
from application.vendors.shared.handlers import VendorCommandHandlers
from application.vendors.shared.query_handlers import VendorQueryHandlers
from application.vendors.portfolio.ports import PortfolioReorderUnitOfWork
from application.vendors.shared.ports import VENDOR_IDEMPOTENCY_RECORD_EXPIRES_AFTER, VendorAggregateUnitOfWork, VendorIdempotencyCompleted, VendorIdempotencyExpired, VendorIdempotencyInProgress, VendorIdempotencyOutcome, VendorIdempotencyPort, VendorIdempotencyRetryableFailed
from application.vendors.analytics.queries import GetVendorAnalyticsQuery, GetVendorDashboardSummaryQuery, ListRecentVendorActivityQuery
from application.vendors.inquiries.queries import ListInquiriesQuery
from application.vendors.packages.queries import ListServicePackagesQuery
from application.vendors.portfolio.queries import ListPortfolioImagesQuery
from application.vendors.profile.queries import GetVendorQuery
from domain.shared.utils import utc_now
from domain.vendors.inquiries.entity import Inquiry
from domain.vendors.packages.entity import PackageApprovalStatus, ServicePackage
from domain.vendors.portfolio.entity import PortfolioImage
from domain.vendors.profile.entity import ServiceCategory, VendorProfile, VendorStatus
from domain.vendors.inquiries.events import InquiryReceived
from domain.vendors.packages.events import ServicePackageCreated
from domain.vendors.portfolio.events import PortfolioMediaReordered
from domain.vendors.profile.events import VendorApproved, VendorProfileUpdated
from domain.vendors.shared.pagination import Page, PageRequest


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


class AggregateUow:
    def __init__(self):
        self.add_calls = []
        self.save_calls = []
        self.events = []
        self.fail_on_add = False
        self.fail_duplicate_on_add = False
        self.fail_on_save = False

    def add_with_pending_events(self, aggregate):
        self.add_calls.append(aggregate)
        if self.fail_duplicate_on_add:
            raise DuplicateVendorProfile()
        if self.fail_on_add:
            raise RuntimeError("creation transaction failed")
        self.events.extend(aggregate.pull_events())
        return aggregate

    def save_with_pending_events(self, aggregate, *, expected_version):
        self.save_calls.append((aggregate, expected_version))
        if self.fail_on_save:
            raise RuntimeError("persistence failed")
        self.events.extend(aggregate.pull_events())
        return aggregate


class VendorRepo:
    def __init__(self, profiles=()):
        self.profiles = {profile.id: profile for profile in profiles}
        self.add_calls = []
        self.save_calls = []
        self.get_by_id_calls = []
        self.get_by_user_id_calls = []
        self.fail_on_save = False
        self.fail_duplicate_on_add = False

    def add(self, profile):
        self.add_calls.append(profile)
        if self.fail_duplicate_on_add:
            raise DuplicateVendorProfile()
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
        self.get_by_user_id_calls.append(user_id)
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


class StrictPortfolioImageCreationPort:
    def __init__(self, order_allocator, aggregate_uow):
        self.order_allocator = order_allocator
        self.aggregate_uow = aggregate_uow
        self.calls = []

    def create_at_next_order(self, *, vendor_id, image_factory):
        if self.aggregate_uow is None:
            raise VendorApplicationConfigurationError(
                field_errors={"aggregate_uow": ["Vendor aggregate unit of work is required."]}
            )
        allocate_next_order = getattr(self.order_allocator, "allocate_next_order", None)
        if not callable(allocate_next_order):
            raise AssertionError("Strict portfolio creation fake requires an order allocator.")
        next_order = allocate_next_order(vendor_id)
        image = image_factory(next_order)
        self.calls.append((vendor_id, image))
        return self.aggregate_uow.add_with_pending_events(image)


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


class InquiryAbuseProtectionPort:
    def __init__(self):
        self.calls = []

    def assert_inquiry_allowed(self, *, requester_identity, vendor_id, payload_digest):
        self.calls.append((requester_identity, vendor_id, payload_digest))


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
        self.events = []
        self.fail = False

    def load_active_vendor_images(self, vendor_id):
        self.list_calls.append(vendor_id)
        return tuple(image for image in self.images if image.vendor_id == vendor_id)

    def list_vendor_images(self, vendor_id, page):
        self.list_calls.append((vendor_id, page))
        items = [image for image in self.images if image.vendor_id == vendor_id]
        return Page(items=items, total=len(items), limit=page.limit, offset=page.offset)

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        self.persist_calls.append((vendor_id, tuple(images), expected_versions))
        if self.fail:
            raise RuntimeError("transaction failed")
        for image in images:
            self.events.extend(image.pull_events())
        return tuple(images)


def _handlers(*, vendor_repo=None, image_repo=None, package_repo=None, inquiry_repo=None, dispatcher=None, **kwargs):
    image_repo = image_repo or ImageRepo()
    kwargs.setdefault("authorization_port", AuthorizationPort())
    kwargs.setdefault("aggregate_uow", AggregateUow())
    kwargs.setdefault("idempotency_port", IdempotencyPort())
    kwargs.setdefault("inquiry_abuse_protection_port", InquiryAbuseProtectionPort())
    kwargs.setdefault("reorder_uow", ReorderUow(()))
    kwargs.setdefault(
        "portfolio_creation_port",
        StrictPortfolioImageCreationPort(image_repo, kwargs["aggregate_uow"]),
    )
    return VendorCommandHandlers(
        vendor_repo=vendor_repo or VendorRepo(),
        image_repo=image_repo,
        package_repo=package_repo or PackageRepo(),
        inquiry_repo=inquiry_repo or InquiryRepo(),
        **kwargs,
    )


def test_profile_creation_uses_creation_unit_of_work_and_idempotency_replays_result():
    idem = IdempotencyPort()
    vendor_repo = VendorRepo()
    aggregate_uow = AggregateUow()
    dispatcher = EventDispatcher()
    handler = _handlers(
        vendor_repo=vendor_repo,
        dispatcher=dispatcher,
        idempotency_port=idem,
        aggregate_uow=aggregate_uow,
    )
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
    assert len(aggregate_uow.add_calls) == 1
    assert vendor_repo.add_calls == []
    assert vendor_repo.save_calls == []
    assert dispatcher.events == []
    fingerprint = idem.executions[0][3]
    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")


def test_profile_creation_translates_duplicate_conflict_from_creation_unit_of_work():
    vendor_repo = VendorRepo()
    aggregate_uow = AggregateUow()
    aggregate_uow.fail_duplicate_on_add = True
    dispatcher = EventDispatcher()
    handler = _handlers(
        vendor_repo=vendor_repo,
        dispatcher=dispatcher,
        idempotency_port=IdempotencyPort(),
        aggregate_uow=aggregate_uow,
    )

    with pytest.raises(VendorConflict) as exc_info:
        handler.create_profile(
            CreateVendorProfileCommand(
                actor=_actor(),
                business_name="Duplicate Vendor",
                category="catering",
                description="Reliable event catering and planning support.",
                service_area="Kigali",
                contact_email="duplicate@example.com",
                contact_phone="+250700000000",
                idempotency_key="duplicate-profile",
            )
        )

    assert exc_info.value.code == "vendor_profile_exists"
    assert len(aggregate_uow.add_calls) == 1
    assert vendor_repo.add_calls == []
    assert vendor_repo.profiles == {}
    assert dispatcher.events == []


def test_profile_aggregate_uow_failure_leaves_no_partial_profile_or_dispatched_events():
    vendor_repo = VendorRepo()
    aggregate_uow = AggregateUow()
    aggregate_uow.fail_on_add = True
    dispatcher = EventDispatcher()
    idempotency_port = IdempotencyPort()
    handler = _handlers(
        vendor_repo=vendor_repo,
        dispatcher=dispatcher,
        idempotency_port=idempotency_port,
        aggregate_uow=aggregate_uow,
    )

    with pytest.raises(RuntimeError, match="creation transaction failed"):
        handler.create_profile(
            CreateVendorProfileCommand(
                actor=_actor(),
                business_name="Atomic Vendor",
                category="catering",
                description="Reliable event catering and planning support.",
                service_area="Kigali",
                contact_email="atomic@example.com",
                contact_phone="+250700000000",
                idempotency_key="failed-profile",
            )
        )

    assert len(aggregate_uow.add_calls) == 1
    assert aggregate_uow.events == []
    assert vendor_repo.add_calls == []
    assert vendor_repo.profiles == {}
    assert dispatcher.events == []
    assert idempotency_port.executions == []


def test_idempotency_payload_fingerprint_is_stable_sha256_hex_digest():
    actor = _actor()
    first = CreateVendorProfileCommand(
        actor=actor,
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key="first-key",
    )
    replay = CreateVendorProfileCommand(
        actor=actor,
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key="replay-key",
    )
    changed = CreateVendorProfileCommand(
        actor=actor,
        business_name="Changed Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key="first-key",
    )

    first_fingerprint = VendorCommandHandlers._payload_fingerprint(first)
    replay_fingerprint = VendorCommandHandlers._payload_fingerprint(replay)
    changed_fingerprint = VendorCommandHandlers._payload_fingerprint(changed)

    assert len(first_fingerprint) == 64
    assert set(first_fingerprint) <= set("0123456789abcdef")
    assert first_fingerprint == replay_fingerprint
    assert first_fingerprint != changed_fingerprint


def test_idempotency_payload_extraction_excludes_original_omitted_command_attributes():
    actor = _actor()
    vendor_id = uuid.uuid4()
    omitted = UpdateVendorProfileCommand(actor=actor, vendor_id=vendor_id, expected_version=3)
    explicit_none = UpdateVendorProfileCommand(
        actor=actor,
        vendor_id=vendor_id,
        expected_version=3,
        website=None,
    )
    explicit_value = UpdateVendorProfileCommand(
        actor=actor,
        vendor_id=vendor_id,
        expected_version=3,
        website="https://vendor.example",
    )

    omitted_fingerprint = VendorCommandHandlers._payload_fingerprint(omitted)
    explicit_none_fingerprint = VendorCommandHandlers._payload_fingerprint(explicit_none)
    explicit_value_fingerprint = VendorCommandHandlers._payload_fingerprint(explicit_value)

    assert len(omitted_fingerprint) == 64
    assert set(omitted_fingerprint) <= set("0123456789abcdef")
    assert omitted_fingerprint != explicit_none_fingerprint
    assert omitted_fingerprint != explicit_value_fingerprint
    assert explicit_none_fingerprint != explicit_value_fingerprint


def test_vendor_aggregate_unit_of_work_contract_persists_one_aggregate_with_pending_events():
    assert hasattr(VendorAggregateUnitOfWork, "add_with_pending_events")
    assert hasattr(VendorAggregateUnitOfWork, "save_with_pending_events")


def test_vendor_idempotency_contract_defines_expiration_and_typed_record_outcomes():
    completed = VendorIdempotencyCompleted(payload_fingerprint="fingerprint", result={"id": "created"})
    in_progress = VendorIdempotencyInProgress(payload_fingerprint="fingerprint")
    retryable_failed = VendorIdempotencyRetryableFailed(payload_fingerprint="fingerprint")
    expired = VendorIdempotencyExpired(payload_fingerprint="fingerprint")
    outcome_types = get_args(VendorIdempotencyOutcome)

    assert VENDOR_IDEMPOTENCY_RECORD_EXPIRES_AFTER == timedelta(hours=24)
    assert completed.status == "completed"
    assert completed.result == {"id": "created"}
    assert in_progress.status == "in_progress"
    assert retryable_failed.status == "retryable_failed"
    assert expired.status == "expired"
    assert {field.name for field in fields(VendorIdempotencyCompleted)} == {
        "payload_fingerprint",
        "result",
        "status",
    }
    assert get_origin(outcome_types[0]) is VendorIdempotencyCompleted
    assert set(outcome_types[1:]) == {
        VendorIdempotencyInProgress,
        VendorIdempotencyRetryableFailed,
        VendorIdempotencyExpired,
    }


def test_vendor_idempotency_port_contract_exposes_outcome_lookup_with_application_expiration():
    signature = inspect.signature(VendorIdempotencyPort.get_outcome)
    hints = get_type_hints(VendorIdempotencyPort.get_outcome)

    assert tuple(signature.parameters) == (
        "self",
        "scope",
        "actor_id",
        "key",
        "payload_fingerprint",
        "expires_after",
    )
    assert signature.parameters["expires_after"].default == VENDOR_IDEMPOTENCY_RECORD_EXPIRES_AFTER
    assert hints["actor_id"] is uuid.UUID
    assert hints["expires_after"] is timedelta
    return_args = get_args(hints["return"])
    outcome_args = tuple(arg for arg in return_args if arg is not type(None))

    assert any(get_origin(arg) is VendorIdempotencyCompleted for arg in outcome_args)
    assert {arg for arg in outcome_args if get_origin(arg) is None} == {
        VendorIdempotencyInProgress,
        VendorIdempotencyRetryableFailed,
        VendorIdempotencyExpired,
    }
    assert type(None) in return_args


def test_vendor_event_dispatcher_application_port_is_removed():
    assert not hasattr(vendor_ports, "VendorEventDispatcher")


def test_vendor_command_handlers_constructor_has_no_event_dispatcher_dependency():
    signature = inspect.signature(VendorCommandHandlers.__init__)

    assert "event_dispatcher" not in signature.parameters


def test_vendor_command_handlers_constructor_requires_reorder_unit_of_work_port():
    hints = get_type_hints(VendorCommandHandlers.__init__)

    assert hints["reorder_uow"] is PortfolioReorderUnitOfWork


@pytest.mark.parametrize(
    "dependency_name",
    (
        "aggregate_uow",
        "authorization_port",
        "idempotency_port",
        "inquiry_abuse_protection_port",
        "reorder_uow",
        "portfolio_creation_port",
    ),
)
def test_vendor_command_handler_required_ports_fail_composition_when_missing(dependency_name):
    with pytest.raises(VendorApplicationConfigurationError) as exc_info:
        _handlers(**{dependency_name: None})

    assert dependency_name in exc_info.value.field_errors


@pytest.mark.parametrize(
    "dependency_name",
    (
        "aggregate_uow",
        "idempotency_port",
        "inquiry_abuse_protection_port",
        "reorder_uow",
        "portfolio_creation_port",
    ),
)
def test_vendor_command_handler_dependencies_fail_composition_for_invalid_protocol_shape(dependency_name):
    with pytest.raises(VendorApplicationConfigurationError) as exc_info:
        _handlers(**{dependency_name: object()})

    assert dependency_name in exc_info.value.field_errors
    assert "Required callable methods are missing:" in exc_info.value.field_errors[dependency_name][0]


def test_vendor_command_handler_required_ports_have_no_constructor_defaults():
    signature = inspect.signature(VendorCommandHandlers.__init__)

    for dependency_name in (
        "aggregate_uow",
        "authorization_port",
        "idempotency_port",
        "inquiry_abuse_protection_port",
        "reorder_uow",
        "portfolio_creation_port",
    ):
        assert signature.parameters[dependency_name].default is inspect.Parameter.empty


def test_vendor_application_configuration_error_has_dedicated_code():
    error = VendorApplicationConfigurationError()

    assert error.code == "vendor_application_configuration_error"
    assert error.message == "Vendor application dependency is not configured."



def test_profile_creation_command_requires_nonblank_idempotency_key():
    idempotency_field = next(field for field in fields(CreateVendorProfileCommand) if field.name == "idempotency_key")

    assert idempotency_field.default is MISSING

    with pytest.raises(TypeError):
        CreateVendorProfileCommand(
            actor=_actor(),
            business_name="New Vendor",
            category="catering",
            description="Reliable event catering and planning support.",
            service_area="Kigali",
            contact_email="new@example.com",
            contact_phone="+250700000000",
        )

    with pytest.raises(InvalidVendorCommand) as none_exc:
        CreateVendorProfileCommand(
            actor=_actor(),
            business_name="New Vendor",
            category="catering",
            description="Reliable event catering and planning support.",
            service_area="Kigali",
            contact_email="new@example.com",
            contact_phone="+250700000000",
            idempotency_key=None,
        )

    with pytest.raises(InvalidVendorCommand) as blank_exc:
        CreateVendorProfileCommand(
            actor=_actor(),
            business_name="New Vendor",
            category="catering",
            description="Reliable event catering and planning support.",
            service_area="Kigali",
            contact_email="new@example.com",
            contact_phone="+250700000000",
            idempotency_key="  ",
        )

    assert none_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}
    assert blank_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}



def test_add_portfolio_image_command_requires_nonblank_idempotency_key():
    idempotency_field = next(field for field in fields(AddPortfolioImageCommand) if field.name == "idempotency_key")

    assert idempotency_field.default is MISSING

    with pytest.raises(TypeError):
        AddPortfolioImageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            public_id="asset",
            secure_url="https://example.com/image.jpg",
        )

    with pytest.raises(InvalidVendorCommand) as none_exc:
        AddPortfolioImageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            public_id="asset",
            secure_url="https://example.com/image.jpg",
            idempotency_key=None,
        )

    with pytest.raises(InvalidVendorCommand) as blank_exc:
        AddPortfolioImageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            public_id="asset",
            secure_url="https://example.com/image.jpg",
            idempotency_key="  ",
        )

    assert none_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}
    assert blank_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}




def test_portfolio_dependencies_require_reorder_uow_and_injected_creation_port():
    with pytest.raises(VendorApplicationConfigurationError) as reorder_exc:
        _handlers(reorder_uow=None)

    signature = inspect.signature(VendorCommandHandlers.__init__)

    assert reorder_exc.value.code == "vendor_application_configuration_error"
    assert str(reorder_exc.value) == "Portfolio reorder requires a unit of work."
    assert signature.parameters["portfolio_creation_port"].default is inspect.Parameter.empty
    assert "order_allocator" not in signature.parameters
    assert not Path("application/vendors/portfolio_image_creation.py").exists()


def test_profile_creation_unit_of_work_failure_is_not_cached_or_dispatched():
    idem = IdempotencyPort()
    vendor_repo = VendorRepo()
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    aggregate_uow.fail_on_add = True
    handler = _handlers(
        vendor_repo=vendor_repo,
        dispatcher=dispatcher,
        aggregate_uow=aggregate_uow,
        idempotency_port=idem,
    )
    cmd = CreateVendorProfileCommand(
        actor=_actor(),
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key="create-profile-fails",
    )

    with pytest.raises(RuntimeError):
        handler.create_profile(cmd)

    assert len(aggregate_uow.add_calls) == 1
    assert aggregate_uow.events == []
    assert vendor_repo.add_calls == []
    assert vendor_repo.save_calls == []
    assert dispatcher.events == []
    assert idem.records == {}


def test_create_profile_duplicate_precheck_and_concurrent_insert_use_same_stable_conflict():
    actor = _actor()
    existing = _profile()
    existing.user_id = actor.user_id
    precheck_repo = VendorRepo([existing])
    precheck_handler = _handlers(vendor_repo=precheck_repo)
    cmd = CreateVendorProfileCommand(
        actor=actor,
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
    )

    with pytest.raises(VendorConflict) as precheck_error:
        precheck_handler.create_profile(cmd)

    concurrent_repo = VendorRepo()
    concurrent_uow = AggregateUow()
    concurrent_uow.fail_duplicate_on_add = True
    concurrent_dispatcher = EventDispatcher()
    concurrent_handler = _handlers(
        vendor_repo=concurrent_repo,
        aggregate_uow=concurrent_uow,
        dispatcher=concurrent_dispatcher,
    )

    with pytest.raises(VendorConflict) as concurrent_error:
        concurrent_handler.create_profile(cmd)

    assert precheck_error.value.code == "vendor_profile_exists"
    assert concurrent_error.value.code == "vendor_profile_exists"
    assert precheck_error.value.message == concurrent_error.value.message
    assert precheck_repo.add_calls == []
    assert concurrent_repo.add_calls == []
    assert len(concurrent_uow.add_calls) == 1
    assert concurrent_dispatcher.events == []


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


def test_idempotency_key_is_trimmed_and_limited_to_200_characters():
    actor = _actor()
    vendor_id = uuid.uuid4()
    max_key = "k" * 200

    create_profile = CreateVendorProfileCommand(
        actor=actor,
        business_name="New Vendor",
        category="catering",
        description="Reliable event catering and planning support.",
        service_area="Kigali",
        contact_email="new@example.com",
        contact_phone="+250700000000",
        idempotency_key=f"  {max_key}  ",
    )
    portfolio = AddPortfolioImageCommand(
        actor=actor,
        vendor_id=vendor_id,
        public_id="asset",
        secure_url="https://example.com/image.jpg",
        idempotency_key=max_key,
    )
    package = CreateServicePackageCommand(
        actor=actor,
        vendor_id=vendor_id,
        name="Standard",
        description="Clear package details for a full event.",
        price=Decimal("5000"),
        idempotency_key=max_key,
    )
    inquiry = SendInquiryCommand(
        vendor_id=vendor_id,
        requester_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support my event?",
        idempotency_key=max_key,
    )

    assert create_profile.idempotency_key == max_key
    assert portfolio.idempotency_key == max_key
    assert package.idempotency_key == max_key
    assert inquiry.idempotency_key == max_key


def test_service_package_creation_command_requires_nonblank_idempotency_key():
    idempotency_field = next(field for field in fields(CreateServicePackageCommand) if field.name == "idempotency_key")

    assert idempotency_field.default is MISSING

    with pytest.raises(TypeError):
        CreateServicePackageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
        )

    with pytest.raises(InvalidVendorCommand) as none_exc:
        CreateServicePackageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
            idempotency_key=None,
        )

    with pytest.raises(InvalidVendorCommand) as blank_exc:
        CreateServicePackageCommand(
            actor=_actor(),
            vendor_id=uuid.uuid4(),
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
            idempotency_key="  ",
        )

    assert none_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}
    assert blank_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}



def test_send_inquiry_command_requires_nonblank_idempotency_key():
    idempotency_field = next(field for field in fields(SendInquiryCommand) if field.name == "idempotency_key")

    assert idempotency_field.default is MISSING

    with pytest.raises(TypeError):
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            requester_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
        )

    with pytest.raises(InvalidVendorCommand) as none_exc:
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            requester_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            idempotency_key=None,
        )

    with pytest.raises(InvalidVendorCommand) as blank_exc:
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            requester_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            idempotency_key="  ",
        )

    assert none_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}
    assert blank_exc.value.field_errors == {"idempotency_key": ["Must be a nonblank string."]}


def test_send_inquiry_command_requires_requester_identifier():
    requester_field = next(field for field in fields(SendInquiryCommand) if field.name == "requester_id")

    assert requester_field.default is MISSING

    with pytest.raises(TypeError):
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            idempotency_key="send-inquiry",
        )

    with pytest.raises(InvalidVendorCommand) as exc_info:
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            requester_id=None,
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            idempotency_key="send-inquiry",
        )

    assert exc_info.value.field_errors == {"requester_id": ["Must be a valid UUID."]}



def test_oversized_idempotency_key_raises_stable_field_error_after_trimming():
    actor = _actor()
    vendor_id = uuid.uuid4()
    oversized = f"  {'k' * 201}  "
    expected_errors = {"idempotency_key": ["Must be 200 characters or fewer."]}

    with pytest.raises(InvalidVendorCommand) as profile_exc:
        CreateVendorProfileCommand(
            actor=actor,
            business_name="New Vendor",
            category="catering",
            description="Reliable event catering and planning support.",
            service_area="Kigali",
            contact_email="new@example.com",
            contact_phone="+250700000000",
            idempotency_key=oversized,
        )
    with pytest.raises(InvalidVendorCommand) as image_exc:
        AddPortfolioImageCommand(
            actor=actor,
            vendor_id=vendor_id,
            public_id="asset",
            secure_url="https://example.com/image.jpg",
            idempotency_key=oversized,
        )
    with pytest.raises(InvalidVendorCommand) as package_exc:
        CreateServicePackageCommand(
            actor=actor,
            vendor_id=vendor_id,
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
            idempotency_key=oversized,
        )
    with pytest.raises(InvalidVendorCommand) as inquiry_exc:
        SendInquiryCommand(
            vendor_id=vendor_id,
            requester_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            idempotency_key=oversized,
        )

    assert profile_exc.value.field_errors == expected_errors
    assert image_exc.value.field_errors == expected_errors
    assert package_exc.value.field_errors == expected_errors
    assert inquiry_exc.value.field_errors == expected_errors


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
                idempotency_key="blocked-portfolio-add",
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
                idempotency_key="blocked-package",
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
    handler = _handlers(
        vendor_repo=vendor_repo,
        image_repo=image_repo,
        dispatcher=dispatcher,
        idempotency_port=IdempotencyPort(),
    )

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                public_id="asset",
                secure_url="https://example.com/image.jpg",
                idempotency_key="missing-portfolio-vendor",
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
    handler = _handlers(
        vendor_repo=vendor_repo,
        image_repo=image_repo,
        dispatcher=dispatcher,
        idempotency_port=IdempotencyPort(),
    )

    with pytest.raises(VendorOperationForbidden) as exc_info:
        handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=profile.id,
                public_id="asset",
                secure_url="https://example.com/image.jpg",
                idempotency_key="forbidden-portfolio-add",
            )
        )

    assert exc_info.value.code == "vendor_portfolio_media_creation_forbidden"
    assert vendor_repo.get_by_id_calls == [profile.id]
    assert image_repo.allocate_next_order_calls == []
    assert image_repo.add_calls == []
    assert dispatcher.events == []


def test_add_portfolio_media_allowed_statuses_use_injected_creation_port():
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
        aggregate_uow = AggregateUow()
        handler = _handlers(
            vendor_repo=vendor_repo,
            image_repo=image_repo,
            aggregate_uow=aggregate_uow,
            idempotency_port=IdempotencyPort(),
        )

        result = handler.add_portfolio_image(
            AddPortfolioImageCommand(
                actor=_actor(),
                vendor_id=profile.id,
                public_id="asset-new",
                secure_url="https://example.com/new-image.jpg",
                idempotency_key=f"allowed-portfolio-add-{status.value}",
            )
        )

        assert result.order == 1
        assert vendor_repo.get_by_id_calls == [profile.id]
        assert image_repo.allocate_next_order_calls == [profile.id]
        assert len(aggregate_uow.add_calls) == 1


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


def test_profile_update_uses_domain_transition_and_atomic_uow_persists_event():
    profile = _profile(version=2)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

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
    assert repo.save_calls == []
    assert aggregate_uow.save_calls == [(profile, 2)]
    assert dispatcher.events == []
    assert len(aggregate_uow.events) == 1
    assert isinstance(aggregate_uow.events[0], VendorProfileUpdated)
    assert aggregate_uow.events[0].aggregate_version == 3


def test_noop_update_does_not_persist_or_emit_events():
    profile = _profile(version=2)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

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
    assert aggregate_uow.save_calls == []
    assert aggregate_uow.events == []
    assert dispatcher.events == []


def test_failed_atomic_persistence_records_no_events():
    profile = _profile(version=1)
    repo = VendorRepo([profile])
    aggregate_uow = AggregateUow()
    aggregate_uow.fail_on_save = True
    dispatcher = EventDispatcher()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

    with pytest.raises(RuntimeError):
        handler.update_profile(
            UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=1, business_name="New")
        )

    assert aggregate_uow.save_calls == [(profile, 1)]
    assert aggregate_uow.events == []
    assert dispatcher.events == []


def test_profile_validation_failure_is_atomic():
    profile = _profile(version=1)
    original = profile.__dict__.copy()
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()

    with pytest.raises(Exception):
        _handlers(vendor_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow).update_profile(
            UpdateVendorProfileCommand(actor=_actor(), vendor_id=profile.id, expected_version=1, contact_email="not-email")
        )

    assert profile.__dict__ == original
    assert repo.save_calls == []
    assert aggregate_uow.save_calls == []
    assert aggregate_uow.events == []
    assert dispatcher.events == []


def test_lifecycle_events_are_persisted_by_aggregate_uow():
    profile = _profile(status=VendorStatus.PENDING_REVIEW, version=7)
    repo = VendorRepo([profile])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(vendor_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

    result = handler.approve_vendor(
        ApproveVendorCommand(moderator=_moderator(), vendor_id=profile.id, expected_version=7)
    )

    assert result.status == VendorStatus.APPROVED.value
    assert repo.save_calls == []
    assert aggregate_uow.save_calls == [(profile, 7)]
    assert dispatcher.events == []
    assert len(aggregate_uow.events) == 1
    assert isinstance(aggregate_uow.events[0], VendorApproved)
    assert aggregate_uow.events[0].event_id
    assert profile.pull_events() == []


def test_service_package_update_uses_owned_lookup_and_single_domain_path():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=5)
    repo = PackageRepo([package])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(package_repo=repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

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
    assert repo.save_calls == []
    assert aggregate_uow.save_calls == [(package, 5)]

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
    requester_id = uuid.uuid4()
    profile = _profile(status=VendorStatus.APPROVED)
    profile.id = vendor_id
    vendor_repo = VendorRepo([profile])
    package_repo = PackageRepo()
    inquiry_repo = InquiryRepo()
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    idempotency_port = IdempotencyPort()
    handler = _handlers(
        vendor_repo=vendor_repo,
        package_repo=package_repo,
        inquiry_repo=inquiry_repo,
        dispatcher=dispatcher,
        aggregate_uow=aggregate_uow,
        idempotency_port=idempotency_port,
    )

    package_result = handler.create_service_package(
        CreateServicePackageCommand(
            actor=_actor(),
            vendor_id=vendor_id,
            name="Standard",
            description="Clear package details for a full event.",
            price=Decimal("5000"),
            idempotency_key="create-package-and-inquiry",
        )
    )
    inquiry_result = handler.send_inquiry(
        SendInquiryCommand(
            vendor_id=vendor_id,
            requester_id=requester_id,
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            event_date=date.today() + timedelta(days=40),
            idempotency_key="send-inquiry-with-package",
        )
    )

    assert package_result.is_active is False
    assert package_repo.add_calls == []
    assert inquiry_repo.add_calls == []
    assert len(aggregate_uow.add_calls) == 2
    assert inquiry_result.event_date == date.today() + timedelta(days=40)
    assert dispatcher.events == []
    assert [type(event) for event in aggregate_uow.events] == [ServicePackageCreated, InquiryReceived]
    inquiry_executions = [
        execution for execution in idempotency_port.executions if execution[0] == "vendor_inquiry.send"
    ]
    assert [execution[1] for execution in inquiry_executions] == [requester_id]
    assert requester_id != vendor_id


def test_create_service_package_loads_vendor_and_returns_stable_missing_vendor_error():
    vendor_id = uuid.uuid4()
    vendor_repo = VendorRepo()
    package_repo = PackageRepo()
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(
        vendor_repo=vendor_repo,
        package_repo=package_repo,
        dispatcher=dispatcher,
        aggregate_uow=aggregate_uow,
        idempotency_port=IdempotencyPort(),
    )

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.create_service_package(
            CreateServicePackageCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                name="Standard",
                description="Clear package details for a full event.",
                price=Decimal("5000"),
                idempotency_key="missing-package-vendor",
            )
        )

    assert exc_info.value.code == "vendor_not_found"
    assert vendor_repo.get_by_id_calls == [vendor_id]
    assert package_repo.add_calls == []
    assert aggregate_uow.add_calls == []
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
        aggregate_uow = AggregateUow()
        handler = _handlers(
            vendor_repo=vendor_repo,
            package_repo=package_repo,
            dispatcher=dispatcher,
            aggregate_uow=aggregate_uow,
            idempotency_port=IdempotencyPort(),
        )

        with pytest.raises(VendorOperationForbidden) as exc_info:
            handler.create_service_package(
                CreateServicePackageCommand(
                    actor=_actor(),
                    vendor_id=profile.id,
                    name="Standard",
                    description="Clear package details for a full event.",
                    price=Decimal("5000"),
                    idempotency_key=f"forbidden-package-{status.value}",
                )
            )

        assert exc_info.value.code == "vendor_service_package_creation_forbidden"
        assert vendor_repo.get_by_id_calls == [profile.id]
        assert package_repo.add_calls == []
        assert aggregate_uow.add_calls == []
        assert dispatcher.events == []


def test_inquiry_command_rejects_datetime_event_date():
    with pytest.raises(InvalidVendorCommand):
        SendInquiryCommand(
            vendor_id=uuid.uuid4(),
            requester_id=uuid.uuid4(),
            client_name="Planner",
            client_email="planner@example.com",
            message="Can you support my event?",
            event_date=datetime.now(),
            idempotency_key="datetime-event-date",
        )


def test_delete_and_activate_vendor_owned_commands_require_vendor_id_and_versions():
    vendor_id = uuid.uuid4()
    image = _image(vendor_id, version=1)
    image_repo = ImageRepo([image])
    package = _package(vendor_id, version=2, status="approved", active=False)
    package_repo = PackageRepo([package])
    dispatcher = EventDispatcher()
    aggregate_uow = AggregateUow()
    handler = _handlers(image_repo=image_repo, package_repo=package_repo, dispatcher=dispatcher, aggregate_uow=aggregate_uow)

    with pytest.raises(InvalidVendorCommand):
        DeletePortfolioImageCommand(actor=_actor(), vendor_id=None, image_id=image.id, expected_version=1)

    handler.delete_portfolio_image(
        DeletePortfolioImageCommand(actor=_actor(), vendor_id=vendor_id, image_id=image.id, expected_version=1)
    )
    handler.activate_package(
        ActivateServicePackageCommand(actor=_actor(), vendor_id=vendor_id, package_id=package.id, expected_version=2)
    )

    assert image_repo.save_calls == []
    assert package_repo.save_calls == []
    assert [call[1] for call in aggregate_uow.save_calls] == [1, 2]


def test_reorder_uses_unit_of_work_to_persist_events_after_success():
    vendor_id = uuid.uuid4()
    first = _image(vendor_id, order=0, version=1)
    second = _image(vendor_id, order=1, version=2)
    uow = ReorderUow([first, second])
    handler = _handlers(reorder_uow=uow)

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
    assert [type(event) for event in uow.events] == [PortfolioMediaReordered, PortfolioMediaReordered]


def test_reorder_failure_records_no_events():
    vendor_id = uuid.uuid4()
    first = _image(vendor_id, order=0, version=1)
    second = _image(vendor_id, order=1, version=2)
    uow = ReorderUow([first, second])
    uow.fail = True
    handler = _handlers(reorder_uow=uow)

    with pytest.raises(RuntimeError):
        handler.reorder_portfolio_images(
            ReorderPortfolioImagesCommand(
                actor=_actor(),
                vendor_id=vendor_id,
                image_ids_in_order=(second.id, first.id),
                expected_versions=(ResourceVersion(second.id, 2), ResourceVersion(first.id, 1)),
            )
        )

    assert uow.events == []


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

    with pytest.raises(VendorApplicationConfigurationError) as read_repo_exc:
        VendorQueryHandlers(VendorRepo(), ImageRepo(), InquiryRepo(), None, auth)
    assert read_repo_exc.value.field_errors == {"read_repo": ["Vendor read port is required."]}
    unauthenticated_query = VendorQueryHandlers(VendorRepo([profile]), ImageRepo([image]), InquiryRepo([inquiry]), read_port)

    assert unauthenticated_query.get_vendor_by_user(profile.user_id).id == profile.id
    with pytest.raises(VendorApplicationConfigurationError) as exc_info:
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
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"add", "save", "pull_events", "dispatch"}:
                    offenders.append(f"{path} calls {node.func.attr} directly")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in manual_event_names:
                offenders.append(f"{path} manually constructs {node.func.id}")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in protected_attrs:
                        offenders.append(f"{path} assigns protected field {target.attr}")

    assert offenders == []
