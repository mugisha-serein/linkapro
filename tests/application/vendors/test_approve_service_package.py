from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from application.vendors.packages.commands import ApproveServicePackageCommand
from application.vendors.shared.commands import AuthenticatedActor, ModeratorActor
from application.vendors.errors import (
    InvalidVendorCommand,
    VendorOperationForbidden,
    VendorResourceNotFound,
    VendorVersionConflict,
)
from application.vendors.shared.handlers import VendorCommandHandlers
from domain.vendors.packages.entity import PackageApprovalStatus, ServicePackage


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


class DenyModerator:
    def __init__(self):
        self.calls = []

    def assert_moderator_can_moderate_vendor(self, moderator, vendor_id):
        self.calls.append((moderator, vendor_id))
        raise VendorOperationForbidden("Moderator cannot approve this package.")


class PackageRepo:
    def __init__(self, packages=()):
        self.packages = {package.id: package for package in packages}
        self.get_for_vendor_calls = []

    def get_for_vendor(self, vendor_id, package_id):
        self.get_for_vendor_calls.append((vendor_id, package_id))
        package = self.packages.get(package_id)
        return package if package and package.vendor_id == vendor_id else None


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


def _package(vendor_id: uuid.UUID, *, version: int = 4) -> ServicePackage:
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


def test_approve_package_command_requires_moderator_and_coerces_ids():
    moderator = ModeratorActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    package_id = uuid.uuid4()

    command = ApproveServicePackageCommand(
        moderator=moderator,
        vendor_id=str(vendor_id),
        package_id=str(package_id),
        expected_version=3,
    )

    assert command.moderator is moderator
    assert command.vendor_id == vendor_id
    assert command.package_id == package_id
    assert command.expected_version == 3

    with pytest.raises(InvalidVendorCommand) as exc_info:
        ApproveServicePackageCommand(
            moderator=AuthenticatedActor(user_id=uuid.uuid4()),
            vendor_id=vendor_id,
            package_id=package_id,
            expected_version=3,
        )

    assert exc_info.value.field_errors == {"moderator": ["Moderator actor is required."]}


def test_approve_package_uses_moderator_authorization_scoped_lookup_and_mutation_contract():
    vendor_id = uuid.uuid4()
    moderator = ModeratorActor(user_id=uuid.uuid4())
    package = _package(vendor_id, version=4)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    authorization = AllowModerator()
    handler = _handler(package_repo, aggregate_uow, authorization)

    result = handler.approve_service_package(
        ApproveServicePackageCommand(
            moderator=moderator,
            vendor_id=vendor_id,
            package_id=package.id,
            expected_version=4,
        )
    )

    assert authorization.calls == [(moderator, vendor_id)]
    assert package_repo.get_for_vendor_calls == [(vendor_id, package.id)]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is package
    assert expected_version == 4
    assert [event.__class__.__name__ for event in aggregate_uow.events] == ["ServicePackageApproved"]
    assert result.id == package.id
    assert result.vendor_id == vendor_id
    assert result.approval_status == PackageApprovalStatus.APPROVED.value
    assert result.rejection_reason is None
    assert result.is_active is False
    assert result.version == 5
    assert package.last_approved_at is not None


def test_approve_package_denied_moderator_does_not_load_or_mutate():
    vendor_id = uuid.uuid4()
    moderator = ModeratorActor(user_id=uuid.uuid4())
    package = _package(vendor_id)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    authorization = DenyModerator()
    handler = _handler(package_repo, aggregate_uow, authorization)

    with pytest.raises(VendorOperationForbidden):
        handler.approve_service_package(
            ApproveServicePackageCommand(
                moderator=moderator,
                vendor_id=vendor_id,
                package_id=package.id,
                expected_version=package.version,
            )
        )

    assert authorization.calls == [(moderator, vendor_id)]
    assert package_repo.get_for_vendor_calls == []
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value
    assert package.version == 4


def test_approve_package_lookup_is_scoped_to_command_vendor():
    owner_vendor_id = uuid.uuid4()
    requested_vendor_id = uuid.uuid4()
    package = _package(owner_vendor_id)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    handler = _handler(package_repo, aggregate_uow, AllowModerator())

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.approve_service_package(
            ApproveServicePackageCommand(
                moderator=ModeratorActor(user_id=uuid.uuid4()),
                vendor_id=requested_vendor_id,
                package_id=package.id,
                expected_version=package.version,
            )
        )

    assert str(exc_info.value) == "Package not found."
    assert package_repo.get_for_vendor_calls == [(requested_vendor_id, package.id)]
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value


def test_approve_package_version_conflict_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=4)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    handler = _handler(package_repo, aggregate_uow, AllowModerator())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.approve_service_package(
            ApproveServicePackageCommand(
                moderator=ModeratorActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                package_id=package.id,
                expected_version=2,
            )
        )

    conflict = exc_info.value
    assert conflict.resource_id == package.id
    assert conflict.expected_version == 2
    assert conflict.actual_version == 4
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value
    assert package.version == 4
    assert package.last_approved_at is None
