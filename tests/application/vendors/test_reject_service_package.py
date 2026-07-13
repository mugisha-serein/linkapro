from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from application.vendors.commands import ModeratorActor, RejectServicePackageCommand
from application.vendors.errors import VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import PackageApprovalStatus, ServicePackage
from domain.vendors.errors import PackageValidationError


class StrictUnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected dependency access: {name}")

    def get_by_id(self, *args, **kwargs): self.__getattr__("get_by_id")
    def get_by_user_id(self, *args, **kwargs): self.__getattr__("get_by_user_id")
    def get_for_vendor(self, *args, **kwargs): self.__getattr__("get_for_vendor")
    def add_with_pending_events(self, *args, **kwargs): self.__getattr__("add_with_pending_events")
    def save_with_pending_events(self, *args, **kwargs): self.__getattr__("save_with_pending_events")
    def assert_actor_owns_vendor(self, *args, **kwargs): self.__getattr__("assert_actor_owns_vendor")
    def assert_actor_can_access_vendor(self, *args, **kwargs): self.__getattr__("assert_actor_can_access_vendor")
    def assert_moderator_can_moderate_vendor(self, *args, **kwargs): self.__getattr__("assert_moderator_can_moderate_vendor")
    def execute_once(self, *args, **kwargs): self.__getattr__("execute_once")
    def assert_inquiry_allowed(self, *args, **kwargs): self.__getattr__("assert_inquiry_allowed")
    def load_active_vendor_images(self, *args, **kwargs): self.__getattr__("load_active_vendor_images")
    def persist_reorder(self, *args, **kwargs): self.__getattr__("persist_reorder")
    def create_at_next_order(self, *args, **kwargs): self.__getattr__("create_at_next_order")


class AllowModerator:
    def __init__(self):
        self.calls = []

    def assert_moderator_can_moderate_vendor(self, moderator, vendor_id):
        self.calls.append((moderator, vendor_id))


class PackageRepo:
    def __init__(self, package):
        self.package = package
        self.get_for_vendor_calls = []

    def get_for_vendor(self, vendor_id, package_id):
        self.get_for_vendor_calls.append((vendor_id, package_id))
        if self.package.vendor_id == vendor_id and self.package.id == package_id:
            return self.package
        return None


class AggregateMutationUow:
    def __init__(self):
        self.save_calls = []
        self.events = []

    def save_with_pending_events(self, aggregate, *, expected_version):
        self.save_calls.append((aggregate, expected_version))
        self.events.extend(aggregate.pull_events())
        return aggregate


class UnusedReorderUow:
    def load_active_vendor_images(self, vendor_id):
        raise AssertionError("Portfolio reorder must not be used.")

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        raise AssertionError("Portfolio reorder must not be used.")


def _package(vendor_id: uuid.UUID, *, version: int = 6) -> ServicePackage:
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Standard package",
        description="A complete service package for professional event support.",
        price=Decimal("50000.00"),
        approval_status=PackageApprovalStatus.WAITING_APPROVAL.value,
        rejection_reason=None,
        is_active=False,
        version=version,
    )


def _handler(package_repo, aggregate_uow, authorization):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=unused,
        image_repo=unused,
        package_repo=package_repo,
        inquiry_repo=unused,
        reorder_uow=UnusedReorderUow(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization,
        idempotency_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
    )


def test_reject_package_succeeds_and_persists_through_application_mutation_contract():
    vendor_id = uuid.uuid4()
    moderator = ModeratorActor(user_id=uuid.uuid4())
    package = _package(vendor_id, version=6)
    package_repo = PackageRepo(package)
    aggregate_uow = AggregateMutationUow()
    authorization = AllowModerator()
    handler = _handler(package_repo, aggregate_uow, authorization)

    result = handler.reject_service_package(
        RejectServicePackageCommand(
            moderator=moderator,
            vendor_id=vendor_id,
            package_id=package.id,
            expected_version=6,
            reason="  Clarify the included deliverables.  ",
        )
    )

    assert authorization.calls == [(moderator, vendor_id)]
    assert package_repo.get_for_vendor_calls == [(vendor_id, package.id)]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is package
    assert expected_version == 6
    assert [event.__class__.__name__ for event in aggregate_uow.events] == ["ServicePackageRejected"]
    assert aggregate_uow.events[0].reason == "Clarify the included deliverables."
    assert result.approval_status == PackageApprovalStatus.REJECTED.value
    assert result.rejection_reason == "Clarify the included deliverables."
    assert result.is_active is False
    assert result.version == 7


def test_reject_package_stale_version_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=6)
    package_repo = PackageRepo(package)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(package_repo, aggregate_uow, AllowModerator())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.reject_service_package(
            RejectServicePackageCommand(
                moderator=ModeratorActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                package_id=package.id,
                expected_version=4,
                reason="Clarify the included deliverables.",
            )
        )

    conflict = exc_info.value
    assert conflict.resource_id == package.id
    assert conflict.expected_version == 4
    assert conflict.actual_version == 6
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value
    assert package.rejection_reason is None
    assert package.version == 6


def test_reject_package_invalid_reason_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=6)
    package_repo = PackageRepo(package)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(package_repo, aggregate_uow, AllowModerator())

    with pytest.raises(PackageValidationError) as exc_info:
        handler.reject_service_package(
            RejectServicePackageCommand(
                moderator=ModeratorActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                package_id=package.id,
                expected_version=6,
                reason="   ",
            )
        )

    assert "rejection_reason" in exc_info.value.field_errors
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value
    assert package.rejection_reason is None
    assert package.version == 6
