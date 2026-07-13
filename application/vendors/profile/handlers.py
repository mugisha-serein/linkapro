from __future__ import annotations

import uuid
from typing import Callable

from domain.vendors.entities import VendorProfile, VendorStatus
from domain.vendors.errors import VendorProfileValidationError
from domain.vendors.interfaces import PageRequest
from application.vendors.errors import DuplicateVendorProfile, InvalidVendorCommand, VendorResourceNotFound
from application.vendors.profile.commands import (
    ApproveVendorCommand,
    CreateVendorProfileCommand,
    ReinstateVendorCommand,
    RejectVendorCommand,
    SubmitVendorForReviewCommand,
    SuspendVendorCommand,
    UpdateVendorBrandingMediaCommand,
    UpdateVendorProfileCommand,
)
from application.vendors.profile.dtos import VendorProfileDTO
from application.vendors.profile.queries import GetVendorQuery
from application.vendors.shared.commands import OMITTED
from application.vendors.shared.dtos import PageDTO


def _translate_profile_update_validation(operation: Callable[[], None]) -> None:
    try:
        operation()
    except VendorProfileValidationError as exc:
        raise InvalidVendorCommand(field_errors=exc.field_errors) from exc


class ProfileCommandHandlersMixin:
        def create_profile(self, cmd: CreateVendorProfileCommand) -> VendorProfileDTO:
            def operation() -> VendorProfileDTO:
                existing = self.vendor_repo.get_by_user_id(cmd.actor.user_id)
                if existing:
                    raise self._vendor_profile_exists_conflict()
                profile = VendorProfile.create_draft(
                    user_id=cmd.actor.user_id,
                    business_name=cmd.business_name,
                    category=cmd.category,
                    description=cmd.description,
                    service_area=cmd.service_area,
                    contact_email=cmd.contact_email,
                    contact_phone=cmd.contact_phone,
                    custom_category=cmd.custom_category,
                    website=cmd.website,
                )
                try:
                    saved = self._add_with_pending_events(profile)
                except DuplicateVendorProfile as exc:
                    raise self._vendor_profile_exists_conflict() from exc
                return self._to_profile_dto(saved)

            return self._run_required_idempotent("vendor_profile.create", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

        def update_profile(self, cmd: UpdateVendorProfileCommand) -> VendorProfileDTO:
            updates = {
                field_name: getattr(cmd, field_name)
                for field_name in (
                    "business_name",
                    "category",
                    "description",
                    "service_area",
                    "contact_email",
                    "contact_phone",
                    "custom_category",
                    "website",
                )
                if getattr(cmd, field_name) is not OMITTED
            }

            def transition(profile: VendorProfile) -> None:
                _translate_profile_update_validation(lambda: profile.update_details(**updates))

            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=transition,
                to_dto=self._to_profile_dto,
            )

        def submit_for_review(self, cmd: SubmitVendorForReviewCommand) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.submit_for_review(),
                to_dto=self._to_profile_dto,
            )

        def approve_vendor(self, cmd: ApproveVendorCommand) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.approve(),
                to_dto=self._to_profile_dto,
            )

        def reject_vendor(self, cmd: RejectVendorCommand) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.reject(cmd.reason),
                to_dto=self._to_profile_dto,
            )

        def suspend_vendor(self, cmd: SuspendVendorCommand) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.suspend(cmd.reason),
                to_dto=self._to_profile_dto,
            )

        def reinstate_vendor(self, cmd: ReinstateVendorCommand) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.reinstate(),
                to_dto=self._to_profile_dto,
            )

        def update_vendor_branding_media(
            self,
            cmd: UpdateVendorBrandingMediaCommand,
        ) -> VendorProfileDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_vendor_or_raise(cmd.vendor_id),
                expected_version=cmd.expected_version,
                transition=lambda profile: profile.update_details(
                    profile_image_url=cmd.profile_image_url,
                    profile_image_public_id=cmd.profile_image_public_id,
                    cover_image_url=cmd.cover_image_url,
                    cover_image_public_id=cmd.cover_image_public_id,
                ),
                to_dto=self._to_profile_dto,
            )


class ProfileQueryHandlersMixin:
        def get_vendor(self, query: GetVendorQuery) -> VendorProfileDTO | None:
            self._assert_actor_can_access_vendor(query)
            profile = self.vendor_repo.get_by_id(query.vendor_id)
            return self._to_profile_dto(profile) if profile else None

        def get_vendor_by_user(self, user_id: uuid.UUID) -> VendorProfileDTO | None:
            profile = self.vendor_repo.get_by_user_id(user_id)
            return self._to_profile_dto(profile) if profile else None

        def list_pending_approvals(self, page: PageRequest | None = None) -> PageDTO[VendorProfileDTO]:
            requested_page = page or PageRequest()
            profiles = self.vendor_repo.list_by_status(VendorStatus.PENDING_REVIEW, requested_page)
            return self._map_page(profiles, self._to_profile_dto)
