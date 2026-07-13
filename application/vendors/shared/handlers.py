from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import uuid
from typing import Callable, Sequence

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from domain.vendors.interfaces import IInquiryRepository, IPortfolioImageRepository, IServicePackageRepository, IVendorProfileRepository
from application.vendors.errors import (
    DuplicateVendorProfile,
    InvalidVendorCommand,
    VendorApplicationConfigurationError,
    VendorConflict,
    VendorResourceNotFound,
    VendorVersionConflict,
)
from application.vendors.inquiries.commands import SendInquiryCommand
from application.vendors.inquiries.dtos import InquiryDTO
from application.vendors.inquiries.ports import InquiryAbuseProtectionPort
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.portfolio.ports import PortfolioImageCreationPort, PortfolioReorderUnitOfWork
from application.vendors.profile.commands import UpdateVendorProfileCommand
from application.vendors.profile.dtos import VendorProfileDTO
from application.vendors.shared.commands import OMITTED
from application.vendors.shared.ports import VendorAggregateUnitOfWork, VendorAuthorizationPort, VendorIdempotencyPort
from application.vendors.shared.transitions import TransitionExecutorMixin


class BaseVendorCommandHandler(TransitionExecutorMixin):
        def __init__(
            self,
            vendor_repo: IVendorProfileRepository,
            image_repo: IPortfolioImageRepository,
            package_repo: IServicePackageRepository,
            inquiry_repo: IInquiryRepository,
            *,
            reorder_uow: PortfolioReorderUnitOfWork,
            aggregate_uow: VendorAggregateUnitOfWork,
            authorization_port: VendorAuthorizationPort,
            idempotency_port: VendorIdempotencyPort,
            inquiry_abuse_protection_port: InquiryAbuseProtectionPort,
            portfolio_creation_port: PortfolioImageCreationPort,
        ):
            self._require_dependency("vendor_repo", vendor_repo, ())
            self._require_dependency("image_repo", image_repo, ())
            self._require_dependency("package_repo", package_repo, ())
            self._require_dependency("inquiry_repo", inquiry_repo, ())
            self._require_dependency(
                "aggregate_uow",
                aggregate_uow,
                ("add_with_pending_events", "save_with_pending_events"),
            )
            self._require_dependency("authorization_port", authorization_port, ())
            self._require_dependency("idempotency_port", idempotency_port, ("execute_once",))
            self._require_dependency(
                "inquiry_abuse_protection_port",
                inquiry_abuse_protection_port,
                ("assert_inquiry_allowed",),
            )
            self._require_dependency(
                "reorder_uow",
                reorder_uow,
                ("load_active_vendor_images", "persist_reorder"),
            )
            self._require_dependency(
                "portfolio_creation_port",
                portfolio_creation_port,
                ("create_at_next_order",),
            )
            self.vendor_repo = vendor_repo
            self.image_repo = image_repo
            self.package_repo = package_repo
            self.inquiry_repo = inquiry_repo
            self.aggregate_uow = aggregate_uow
            self.authorization_port = authorization_port
            self.idempotency_port = idempotency_port
            self.inquiry_abuse_protection_port = inquiry_abuse_protection_port
            self.reorder_uow = reorder_uow
            self.portfolio_creation_port = portfolio_creation_port

        @staticmethod
        def _require_dependency(name: str, dependency, required_methods: Sequence[str]) -> None:
            if dependency is None:
                raise VendorApplicationConfigurationError(field_errors={name: ["Required dependency is missing."]})
            missing_methods = []
            for method_name in required_methods:
                try:
                    method = getattr(dependency, method_name)
                except (AttributeError, AssertionError):
                    method = None
                if not callable(method):
                    missing_methods.append(method_name)
            if missing_methods:
                detail = f"Required callable methods are missing: {', '.join(missing_methods)}."
                raise VendorApplicationConfigurationError(field_errors={name: [detail]})

        def _get_vendor_or_raise(self, vendor_id: uuid.UUID) -> VendorProfile:
            profile = self.vendor_repo.get_by_id(vendor_id)
            if not profile:
                raise VendorResourceNotFound("Vendor not found.")
            return profile

        def _get_package_or_raise(self, vendor_id: uuid.UUID, package_id: uuid.UUID) -> ServicePackage:
            package = self.package_repo.get_for_vendor(vendor_id, package_id)
            if not package:
                raise VendorResourceNotFound("Package not found.")
            return package

        def _get_image_or_raise(self, vendor_id: uuid.UUID, image_id: uuid.UUID) -> PortfolioImage:
            image = self.image_repo.get_for_vendor(vendor_id, image_id)
            if not image:
                raise VendorResourceNotFound("Image not found.")
            return image

        def _get_inquiry_or_raise(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> Inquiry:
            inquiry = self.inquiry_repo.get_for_vendor(vendor_id, inquiry_id)
            if not inquiry:
                raise VendorResourceNotFound("Inquiry not found.")
            return inquiry

        @staticmethod
        def _vendor_profile_exists_conflict() -> VendorConflict:
            return VendorConflict(
                "User already has a vendor profile.",
                code="vendor_profile_exists",
            )

        def _assert_actor_owns_vendor(self, actor, vendor_id: uuid.UUID) -> None:
            self.authorization_port.assert_actor_owns_vendor(actor, vendor_id)

        def _assert_moderator_can_moderate_vendor(self, moderator, vendor_id: uuid.UUID) -> None:
            self.authorization_port.assert_moderator_can_moderate_vendor(moderator, vendor_id)

        def _assert_inquiry_allowed(
            self,
            *,
            requester_identity: uuid.UUID,
            vendor_id: uuid.UUID,
            payload_digest: str,
        ) -> None:
            self.inquiry_abuse_protection_port.assert_inquiry_allowed(
                requester_identity=requester_identity,
                vendor_id=vendor_id,
                payload_digest=payload_digest,
            )

        def _save_if_changed(self, aggregate, original_version: int, to_dto: Callable):
            if aggregate.version == original_version:
                return to_dto(aggregate)
            saved = self._save_with_pending_events(aggregate, original_version)
            return to_dto(saved)

        def _add_with_pending_events(self, aggregate):
            return self.aggregate_uow.add_with_pending_events(aggregate)

        def _save_with_pending_events(self, aggregate, expected_version: int):
            return self.aggregate_uow.save_with_pending_events(aggregate, expected_version=expected_version)

        @staticmethod
        def _reject_blank_required_profile_updates(cmd: UpdateVendorProfileCommand) -> None:
            required_fields = VendorProfile.required_profile_fields()
            blank_fields = [
                field_name
                for field_name in required_fields
                if getattr(cmd, field_name) is not None and not str(getattr(cmd, field_name)).strip()
            ]
            if blank_fields:
                raise ValueError(f"Required vendor profile fields cannot be blank: {', '.join(blank_fields)}")

        @staticmethod
        def _assert_expected_version(
            resource_id: uuid.UUID,
            actual_version: int,
            expected_version: int,
        ) -> None:
            if expected_version != actual_version:
                raise VendorVersionConflict(
                    resource_id=resource_id,
                    expected_version=expected_version,
                    actual_version=actual_version,
                )

        def _load_active_vendor_images(self, vendor_id: uuid.UUID) -> tuple[PortfolioImage, ...]:
            return tuple(self.reorder_uow.load_active_vendor_images(vendor_id))

        @staticmethod
        def _validate_portfolio_reorder_ids(
            requested_ids: Sequence[uuid.UUID], image_map: dict[uuid.UUID, PortfolioImage]
        ) -> None:
            if not requested_ids:
                raise InvalidVendorCommand(field_errors={"image_ids_in_order": ["Portfolio image order is required."]})
            if len(requested_ids) != len(set(requested_ids)):
                raise InvalidVendorCommand(field_errors={"image_ids_in_order": ["Duplicate portfolio images are not allowed."]})
            if set(requested_ids) != set(image_map.keys()):
                raise VendorResourceNotFound("Image not found.")

        def _run_idempotent(self, scope: str, actor_id: uuid.UUID, key: str | None, cmd, operation: Callable):
            if key is None:
                return operation()
            return self._run_required_idempotent(scope, actor_id, key, cmd, operation)

        def _run_required_idempotent(self, scope: str, actor_id: uuid.UUID, key: str, cmd, operation: Callable):
            fingerprint = self._payload_fingerprint(cmd)
            return self.idempotency_port.execute_once(
                scope=scope,
                actor_id=actor_id,
                key=key,
                payload_fingerprint=fingerprint,
                operation=operation,
            )

        @staticmethod
        def _payload_fingerprint(cmd) -> str:
            if is_dataclass(cmd):
                payload = {field.name: getattr(cmd, field.name) for field in fields(cmd)}
            else:
                payload = dict(cmd)
            payload.pop("idempotency_key", None)
            payload = {key: value for key, value in payload.items() if value is not OMITTED}
            canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

        @staticmethod
        def _inquiry_payload_digest(cmd: SendInquiryCommand) -> str:
            payload = {
                "client_email": cmd.client_email,
                "client_name": cmd.client_name,
                "client_phone": cmd.client_phone,
                "event_date": cmd.event_date,
                "message": cmd.message,
            }
            canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

        @staticmethod
        def _to_profile_dto(profile: VendorProfile) -> VendorProfileDTO:
            return VendorProfileDTO(
                id=profile.id,
                user_id=profile.user_id,
                business_name=profile.business_name,
                category=profile.category.value,
                description=profile.description,
                service_area=profile.service_area,
                contact_email=profile.contact_email,
                contact_phone=profile.contact_phone,
                custom_category=profile.custom_category,
                website=profile.website,
                status=profile.status.value,
                profile_image_url=profile.profile_image_url,
                cover_image_url=profile.cover_image_url,
                submitted_at=profile.submitted_at,
                approved_at=profile.approved_at,
                rejected_at=profile.rejected_at,
                rejection_reason=profile.rejection_reason,
                version=profile.version,
            )

        @staticmethod
        def _to_image_dto(image: PortfolioImage) -> PortfolioImageDTO:
            return PortfolioImageDTO(
                id=image.id,
                vendor_id=image.vendor_id,
                secure_url=image.secure_url,
                caption=image.caption,
                order=image.order,
                media_type=image.media_type,
                upload_status=image.upload_status,
                quality_status=image.quality_status,
                visibility_status=image.visibility_status,
                upload_error=image.upload_error,
                failure_reason=image.failure_reason,
                rejection_reason=image.rejection_reason,
                original_filename=image.original_filename,
                mime_type=image.mime_type,
                file_size=image.file_size,
                local_preview_url=image.local_preview_url,
                cloudinary_public_id=image.cloudinary_public_id,
                cloudinary_secure_url=image.cloudinary_secure_url,
                width=image.width,
                height=image.height,
                duration_seconds=image.duration_seconds,
                analyzer_score=image.analyzer_score,
                analyzer_summary=image.analyzer_summary,
                is_active=image.is_active,
                is_deleted=image.is_deleted,
                deleted_at=image.deleted_at,
                version=image.version,
            )

        @staticmethod
        def _to_package_dto(package: ServicePackage) -> ServicePackageDTO:
            return ServicePackageDTO(
                id=package.id,
                vendor_id=package.vendor_id,
                name=package.name,
                description=package.description,
                price=package.price,
                currency=package.currency,
                package_tier=package.package_tier,
                approval_status=package.approval_status,
                rejection_reason=package.rejection_reason,
                is_active=package.is_active,
                is_deleted=package.is_deleted,
                deleted_at=package.deleted_at,
                last_approved_at=package.last_approved_at,
                last_vendor_public_edit_at=package.last_vendor_public_edit_at,
                next_vendor_edit_allowed_at=package.next_vendor_edit_allowed_at,
                version=package.version,
            )

        @staticmethod
        def _to_inquiry_dto(inquiry: Inquiry) -> InquiryDTO:
            return InquiryDTO(
                id=inquiry.id,
                vendor_id=inquiry.vendor_id,
                client_name=inquiry.client_name,
                client_email=inquiry.client_email,
                client_phone=inquiry.client_phone,
                message=inquiry.message,
                event_date=inquiry.event_date,
                is_read=inquiry.is_read,
                created_at=inquiry.created_at,
                version=inquiry.version,
            )
