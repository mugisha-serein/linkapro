from __future__ import annotations

from domain.vendors.packages.entity import ServicePackage
from domain.vendors.profile.entity import VendorProfile, VendorStatus
from domain.vendors.shared.pagination import PageRequest
from application.vendors.packages.commands import (
    ActivateServicePackageCommand,
    ApproveServicePackageCommand,
    CreateServicePackageCommand,
    DeactivateServicePackageCommand,
    RejectServicePackageCommand,
    RestoreServicePackageForReviewCommand,
    SubmitServicePackageForApprovalCommand,
    UpdateServicePackageCommand,
)
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.packages.queries import ListServicePackagesQuery
from application.vendors.shared.dtos import PageDTO
from application.vendors.errors import VendorOperationForbidden, VendorResourceNotFound


SERVICE_PACKAGE_CREATION_ALLOWED_STATUSES = frozenset({VendorStatus.APPROVED})


def ensure_vendor_can_create_service_package(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorResourceNotFound("Vendor not found.", code="vendor_not_found")
    if profile.status not in SERVICE_PACKAGE_CREATION_ALLOWED_STATUSES:
        raise VendorOperationForbidden(
            "Vendor must be approved before creating service packages.",
            code="vendor_service_package_creation_forbidden",
        )



class PackageCommandHandlersMixin:
        def create_service_package(self, cmd: CreateServicePackageCommand) -> ServicePackageDTO:
            self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)

            def operation() -> ServicePackageDTO:
                profile = self.vendor_repo.get_by_id(cmd.vendor_id)
                ensure_vendor_can_create_service_package(profile)
                package = ServicePackage.create(
                    vendor_id=cmd.vendor_id,
                    name=cmd.name,
                    description=cmd.description,
                    price=cmd.price,
                    currency=cmd.currency,
                    package_tier=cmd.package_tier,
                )
                saved = self._add_with_pending_events(package)
                return self._to_package_dto(saved)

            return self._run_required_idempotent("service_package.create", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

        def update_service_package(self, cmd: UpdateServicePackageCommand) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.update_details(
                    cmd.name,
                    cmd.description,
                    cmd.price,
                    cmd.currency,
                    cmd.package_tier,
                ),
                to_dto=self._to_package_dto,
            )

        def submit_service_package_for_approval(
            self,
            cmd: SubmitServicePackageForApprovalCommand,
        ) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.submit_for_approval(),
                to_dto=self._to_package_dto,
            )

        def approve_service_package(self, cmd: ApproveServicePackageCommand) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.approve(),
                to_dto=self._to_package_dto,
            )

        def reject_service_package(self, cmd: RejectServicePackageCommand) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.reject(cmd.reason),
                to_dto=self._to_package_dto,
            )

        def restore_service_package_for_review(
            self,
            cmd: RestoreServicePackageForReviewCommand,
        ) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.restore_to_waiting_approval(),
                to_dto=self._to_package_dto,
            )

        def deactivate_package(self, cmd: DeactivateServicePackageCommand) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.deactivate(),
                to_dto=self._to_package_dto,
            )

        def activate_package(self, cmd: ActivateServicePackageCommand) -> ServicePackageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_package_or_raise(cmd.vendor_id, cmd.package_id),
                expected_version=cmd.expected_version,
                transition=lambda package: package.activate(),
                to_dto=self._to_package_dto,
            )


class PackageQueryHandlersMixin:
        def list_service_packages(self, query: ListServicePackagesQuery) -> PageDTO[ServicePackageDTO]:
            self._assert_actor_can_access_vendor(query)
            return self.read_repo.list_service_packages(query.vendor_id, query.page or PageRequest())
