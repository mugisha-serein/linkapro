from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from application.vendors.commands import (
    AuthenticatedActor,
    SubmitServicePackageForApprovalCommand,
)
from application.vendors.errors import VendorResourceNotFound, VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import PackageApprovalStatus, ServicePackage


class StrictUnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected dependency access: {name}")


class AllowOwner:
    def __init__(self):
        self.calls = []

    def assert_actor_owns_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))


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


def _package(vendor_id: uuid.UUID, *, version: int = 4, status: str = PackageApprovalStatus.REJECTED.value):
    return ServicePackage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        name="Standard package",
        description="A complete service package for professional event support.",
        price=Decimal("50000.00"),
        approval_status=status,
        rejection_reason="Clarify package deliverables." if status == PackageApprovalStatus.REJECTED.value else None,
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
        event_dispatcher=unused,
        reorder_uow=UnusedReorderUow(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization,
        portfolio_creation_port=None,
    )


def test_submit_package_command_coerces_ids_and_expected_version():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    package_id = uuid.uuid4()

    command = SubmitServicePackageForApprovalCommand(
        actor=actor,
        vendor_id=str(vendor_id),
        package_id=str(package_id),
        expected_version=3,
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.package_id == package_id
    assert command.expected_version == 3


def test_submit_package_uses_scoped_lookup_transition_and_application_mutation_contract():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    package = _package(vendor_id, version=4)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    authorization = AllowOwner()
    handler = _handler(package_repo, aggregate_uow, authorization)

    result = handler.submit_service_package_for_approval(
        SubmitServicePackageForApprovalCommand(
            actor=actor,
            vendor_id=vendor_id,
            package_id=package.id,
            expected_version=4,
        )
    )

    assert authorization.calls == [(actor, vendor_id)]
    assert package_repo.get_for_vendor_calls == [(vendor_id, package.id)]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is package
    assert expected_version == 4
    assert [event.__class__.__name__ for event in aggregate_uow.events] == [
        "ServicePackageSubmittedForApproval"
    ]
    assert result.id == package.id
    assert result.vendor_id == vendor_id
    assert result.approval_status == PackageApprovalStatus.WAITING_APPROVAL.value
    assert result.rejection_reason is None
    assert result.is_active is False
    assert result.version == 5


def test_submit_package_lookup_is_scoped_to_command_vendor():
    owner_vendor_id = uuid.uuid4()
    requested_vendor_id = uuid.uuid4()
    package = _package(owner_vendor_id)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    authorization = AllowOwner()
    handler = _handler(package_repo, aggregate_uow, authorization)

    with pytest.raises(VendorResourceNotFound) as exc_info:
        handler.submit_service_package_for_approval(
            SubmitServicePackageForApprovalCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=requested_vendor_id,
                package_id=package.id,
                expected_version=package.version,
            )
        )

    assert str(exc_info.value) == "Package not found."
    assert package_repo.get_for_vendor_calls == [(requested_vendor_id, package.id)]
    assert aggregate_uow.save_calls == []
    assert package.approval_status == PackageApprovalStatus.REJECTED.value


def test_submit_package_version_conflict_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    package = _package(vendor_id, version=4)
    package_repo = PackageRepo((package,))
    aggregate_uow = AggregateMutationUow()
    handler = _handler(package_repo, aggregate_uow, AllowOwner())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.submit_service_package_for_approval(
            SubmitServicePackageForApprovalCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
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
    assert package.approval_status == PackageApprovalStatus.REJECTED.value
    assert package.version == 4
