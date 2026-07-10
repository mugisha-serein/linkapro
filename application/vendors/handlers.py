from __future__ import annotations

from dataclasses import fields, is_dataclass
import hashlib
import json
import uuid
from typing import Callable, Sequence

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile, VendorStatus
from domain.vendors.errors import VendorProfileValidationError
from domain.vendors.inquiry_policy import ensure_vendor_can_receive_inquiry
from domain.vendors.interfaces import (
    IInquiryRepository,
    IPortfolioImageRepository,
    IServicePackageRepository,
    IVendorProfileRepository,
    Page,
    PageRequest,
)

from .commands import (
    ActivateServicePackageCommand,
    AddPortfolioImageCommand,
    ApproveServicePackageCommand,
    ApproveVendorCommand,
    AuthenticatedActor,
    CreateServicePackageCommand,
    CreateVendorProfileCommand,
    DeactivateServicePackageCommand,
    DeletePortfolioImageCommand,
    MarkInquiryReadCommand,
    ModeratorActor,
    OMITTED,
    ReinstateVendorCommand,
    RejectServicePackageCommand,
    RejectVendorCommand,
    ReorderPortfolioImagesCommand,
    RestoreServicePackageForReviewCommand,
    SendInquiryCommand,
    SubmitServicePackageForApprovalCommand,
    SubmitVendorForReviewCommand,
    SuspendVendorCommand,
    UpdateServicePackageCommand,
    UpdateVendorProfileCommand,
)
from .dtos import (
    InquiryDTO,
    PageDTO,
    PortfolioImageDTO,
    ServicePackageDTO,
    VendorActivityDTO,
    VendorAnalyticsDTO,
    VendorDashboardSummaryDTO,
    VendorProfileDTO,
)
from .errors import (
    DuplicateVendorProfile,
    InvalidVendorCommand,
    VendorConflict,
    VendorOperationForbidden,
    InvalidVendorCommand,
    VendorApplicationConfigurationError,
    VendorConflict,
    VendorResourceNotFound,
    VendorVersionConflict,
)
from .ports import (
    InquiryAbuseProtectionPort,
    PortfolioImageCreationPort,
    PortfolioReorderUnitOfWork,
    VendorAggregateUnitOfWork,
    VendorAuthorizationPort,
    VendorIdempotencyPort,
    VendorReadPort,
)
from .portfolio_media_policy import ensure_vendor_can_add_portfolio_media
from .queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    GetVendorQuery,
    ListInquiriesQuery,
    ListPortfolioImagesQuery,
    ListRecentVendorActivityQuery,
    ListServicePackagesQuery,
)
from .service_package_policy import ensure_vendor_can_create_service_package



def _translate_profile_update_validation(operation: Callable[[], None]) -> None:
    try:
        operation()
    except VendorProfileValidationError as exc:
        raise InvalidVendorCommand(field_errors=exc.field_errors) from exc


class VendorCommandHandlers:
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
        self._require_dependency("vendor_repo", vendor_repo, ("get_by_id", "get_by_user_id"))
        self._require_dependency("image_repo", image_repo, ("get_for_vendor",))
        self._require_dependency("package_repo", package_repo, ("get_for_vendor",))
        self._require_dependency("inquiry_repo", inquiry_repo, ("get_for_vendor",))
        self._require_dependency(
            "aggregate_uow",
            aggregate_uow,
            ("add_with_pending_events", "save_with_pending_events"),
        )
        self._require_dependency(
            "authorization_port",
            authorization_port,
            (
                "assert_actor_owns_vendor",
                "assert_actor_can_access_vendor",
                "assert_moderator_can_moderate_vendor",
            ),
        )
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
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
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
        _translate_profile_update_validation(lambda: profile.update_details(**updates))
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def submit_for_review(self, cmd: SubmitVendorForReviewCommand) -> VendorProfileDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
        profile.submit_for_review()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def approve_vendor(self, cmd: ApproveVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
        profile.approve()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def reject_vendor(self, cmd: RejectVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
        profile.reject(cmd.reason)
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def suspend_vendor(self, cmd: SuspendVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
        profile.suspend(cmd.reason)
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def reinstate_vendor(self, cmd: ReinstateVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.id, profile.version, cmd.expected_version)
        original_version = profile.version
        profile.reinstate()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def add_portfolio_image(self, cmd: AddPortfolioImageCommand) -> PortfolioImageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)

        def operation() -> PortfolioImageDTO:
            profile = self.vendor_repo.get_by_id(cmd.vendor_id)
            ensure_vendor_can_add_portfolio_media(profile)
            def image_factory(next_order: int) -> PortfolioImage:
                return PortfolioImage(
                    id=uuid.uuid4(),
                    vendor_id=cmd.vendor_id,
                    public_id=cmd.public_id,
                    secure_url=cmd.secure_url,
                    caption=cmd.caption,
                    order=next_order,
                )

            saved = self.portfolio_creation_port.create_at_next_order(
                vendor_id=cmd.vendor_id,
                image_factory=image_factory,
            )
            return self._to_image_dto(saved)

        return self._run_required_idempotent("portfolio_image.add", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

    def delete_portfolio_image(self, cmd: DeletePortfolioImageCommand) -> None:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        image = self.image_repo.get_for_vendor(cmd.vendor_id, cmd.image_id)
        if not image:
            raise VendorResourceNotFound("Image not found.")
        self._assert_expected_version(image.id, image.version, cmd.expected_version)
        original_version = image.version
        image.deactivate()
        if image.version == original_version:
            return
        self._save_with_pending_events(image, original_version)

    def reorder_portfolio_images(self, cmd: ReorderPortfolioImagesCommand) -> PageDTO[PortfolioImageDTO]:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        images = self._load_active_vendor_images(cmd.vendor_id)
        image_map = {image.id: image for image in images}
        requested_ids = tuple(cmd.image_ids_in_order)
        self._validate_portfolio_reorder_ids(requested_ids, image_map)
        expected_versions = {item.resource_id: item.expected_version for item in cmd.expected_versions}
        if set(expected_versions) != set(requested_ids):
            raise InvalidVendorCommand(field_errors={"expected_versions": ["Expected versions must match image order."]})
        for image_id, expected_version in expected_versions.items():
            self._assert_expected_version(image_id, image_map[image_id].version, expected_version)

        changed: list[PortfolioImage] = []
        for index, image_id in enumerate(requested_ids):
            image = image_map[image_id]
            if image.order == index:
                continue
            image.reorder(index)
            changed.append(image)

        if changed:
            persisted = tuple(
                self.reorder_uow.persist_reorder(cmd.vendor_id, changed, expected_versions=expected_versions)
            )
            image_map.update({image.id: image for image in persisted})

        ordered = tuple(self._to_image_dto(image_map[image_id]) for image_id in requested_ids)
        return PageDTO(items=ordered, total=len(images), limit=len(images), offset=0)

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
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.update_details(cmd.name, cmd.description, cmd.price, cmd.currency, cmd.package_tier)
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def submit_service_package_for_approval(
        self,
        cmd: SubmitServicePackageForApprovalCommand,
    ) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.submit_for_approval()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def approve_service_package(self, cmd: ApproveServicePackageCommand) -> ServicePackageDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.approve()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def reject_service_package(self, cmd: RejectServicePackageCommand) -> ServicePackageDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.reject(cmd.reason)
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def restore_service_package_for_review(
        self,
        cmd: RestoreServicePackageForReviewCommand,
    ) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.restore_to_waiting_approval()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def deactivate_package(self, cmd: DeactivateServicePackageCommand) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.deactivate()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def activate_package(self, cmd: ActivateServicePackageCommand) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.id, package.version, cmd.expected_version)
        original_version = package.version
        package.activate()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def send_inquiry(self, cmd: SendInquiryCommand) -> InquiryDTO:
        payload_digest = self._inquiry_payload_digest(cmd)

        def operation() -> InquiryDTO:
            self._assert_inquiry_allowed(
                requester_identity=cmd.requester_id,
                vendor_id=cmd.vendor_id,
                payload_digest=payload_digest,
            )
            profile = self.vendor_repo.get_by_id(cmd.vendor_id)
            ensure_vendor_can_receive_inquiry(profile)
            inquiry = Inquiry.create(
                vendor_id=cmd.vendor_id,
                client_name=cmd.client_name,
                client_email=cmd.client_email,
                client_phone=cmd.client_phone,
                message=cmd.message,
                event_date=cmd.event_date,
            )
            saved = self._add_with_pending_events(inquiry)
            return self._to_inquiry_dto(saved)

        return self._run_required_idempotent(
            "vendor_inquiry.send", cmd.requester_id, cmd.idempotency_key, cmd, operation
        )

    def mark_inquiry_read(self, cmd: MarkInquiryReadCommand) -> InquiryDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        inquiry = self.inquiry_repo.get_for_vendor(cmd.vendor_id, cmd.inquiry_id)
        if not inquiry:
            raise VendorResourceNotFound("Inquiry not found.")
        self._assert_expected_version(inquiry.id, inquiry.version, cmd.expected_version)
        original_version = inquiry.version
        inquiry.mark_read()
        return self._save_if_changed(inquiry, original_version, self._to_inquiry_dto)

    @staticmethod
    def _require_dependency(name: str, dependency, required_methods: Sequence[str]) -> None:
        missing_methods = []
        for method_name in required_methods:
            try:
                method = getattr(dependency, method_name)
            except (AttributeError, AssertionError):
                method = None
            if not callable(method):
                missing_methods.append(method_name)
        if dependency is None or missing_methods:
            detail = "Required dependency is missing."
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
    def _vendor_profile_exists_conflict() -> VendorConflict:
        return VendorConflict("User already has a vendor profile.", code="vendor_profile_exists")

    def _assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None:
        self.authorization_port.assert_actor_owns_vendor(actor, vendor_id)

    def _assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None:
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


class VendorQueryHandlers:
    def __init__(
        self,
        vendor_repo: IVendorProfileRepository,
        image_repo: IPortfolioImageRepository,
        inquiry_repo: IInquiryRepository,
        read_repo: VendorReadPort,
        authorization_port: VendorAuthorizationPort | None = None,
    ):
        if read_repo is None:
            raise VendorApplicationConfigurationError(field_errors={"read_repo": ["Vendor read port is required."]})
        self.vendor_repo = vendor_repo
        self.image_repo = image_repo
        self.inquiry_repo = inquiry_repo
        self.read_repo = read_repo
        self.authorization_port = authorization_port

    def get_vendor(self, query: GetVendorQuery) -> VendorProfileDTO | None:
        self._assert_actor_can_access_vendor(query)
        profile = self.vendor_repo.get_by_id(query.vendor_id)
        return VendorCommandHandlers._to_profile_dto(profile) if profile else None

    def get_vendor_by_user(self, user_id: uuid.UUID) -> VendorProfileDTO | None:
        profile = self.vendor_repo.get_by_user_id(user_id)
        return VendorCommandHandlers._to_profile_dto(profile) if profile else None

    def list_pending_approvals(self, page: PageRequest | None = None) -> PageDTO[VendorProfileDTO]:
        requested_page = page or PageRequest()
        profiles = self.vendor_repo.list_by_status(VendorStatus.PENDING_REVIEW, requested_page)
        return self._map_page(profiles, VendorCommandHandlers._to_profile_dto)

    def list_portfolio_images(self, query: ListPortfolioImagesQuery) -> PageDTO[PortfolioImageDTO]:
        self._assert_actor_can_access_vendor(query)
        images = self.image_repo.list_by_vendor(query.vendor_id, query.page or PageRequest())
        return self._map_page(images, VendorCommandHandlers._to_image_dto)

    def list_service_packages(self, query: ListServicePackagesQuery) -> PageDTO[ServicePackageDTO]:
        self._assert_actor_can_access_vendor(query)
        return self.read_repo.list_service_packages(query.vendor_id, query.page or PageRequest())

    def list_inquiries(self, query: ListInquiriesQuery) -> PageDTO[InquiryDTO]:
        self._assert_actor_can_access_vendor(query)
        inquiries = self.inquiry_repo.list_by_vendor(query.vendor_id, query.page or PageRequest())
        return self._map_page(inquiries, VendorCommandHandlers._to_inquiry_dto)

    def get_dashboard_summary(self, query: GetVendorDashboardSummaryQuery) -> VendorDashboardSummaryDTO:
        self._assert_actor_can_access_vendor(query)
        if self.vendor_repo.get_by_id(query.vendor_id) is None:
            raise VendorResourceNotFound("Vendor not found.")
        return self.read_repo.dashboard_summary(query.vendor_id)

    def get_analytics(self, query: GetVendorAnalyticsQuery) -> VendorAnalyticsDTO:
        self._assert_actor_can_access_vendor(query)
        return self.read_repo.analytics(query.vendor_id)

    def get_recent_activity(self, query: ListRecentVendorActivityQuery) -> PageDTO[VendorActivityDTO]:
        self._assert_actor_can_access_vendor(query)
        return self.read_repo.recent_activity(query.vendor_id, query.page or PageRequest(limit=10, offset=0))

    def _assert_actor_can_access_vendor(
        self,
        query: (
            GetVendorQuery
            | ListPortfolioImagesQuery
            | ListServicePackagesQuery
            | ListInquiriesQuery
            | GetVendorDashboardSummaryQuery
            | GetVendorAnalyticsQuery
            | ListRecentVendorActivityQuery
        ),
    ) -> None:
        if self.authorization_port is None:
            raise VendorApplicationConfigurationError(
                field_errors={"authorization_port": ["Vendor authorization is required."]}
            )
        self.authorization_port.assert_actor_can_access_vendor(query.actor, query.vendor_id)

    @staticmethod
    def _map_page(page: Page, mapper: Callable) -> PageDTO:
        return PageDTO(
            items=tuple(mapper(item) for item in page.items),
            total=page.total,
            limit=page.limit,
            offset=page.offset,
            next_cursor=page.next_cursor,
        )
