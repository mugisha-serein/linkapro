from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import uuid
from typing import Callable, Sequence

from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile, VendorStatus
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
    RejectVendorCommand,
    ReorderPortfolioImagesCommand,
    SendInquiryCommand,
    SubmitVendorForReviewCommand,
    SuspendVendorCommand,
    UpdateServicePackageCommand,
    UpdateVendorProfileCommand,
)
from .dtos import InquiryDTO, PageDTO, PortfolioImageDTO, ServicePackageDTO, VendorProfileDTO
from .errors import InvalidVendorCommand, VendorConflict, VendorOperationForbidden, VendorResourceNotFound
from .ports import (
    PortfolioOrderAllocator,
    PortfolioReorderUnitOfWork,
    VendorAggregateUnitOfWork,
    VendorAuthorizationPort,
    VendorCreationUnitOfWork,
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


class VendorCommandHandlers:
    def __init__(
        self,
        vendor_repo: IVendorProfileRepository,
        image_repo: IPortfolioImageRepository,
        package_repo: IServicePackageRepository,
        inquiry_repo: IInquiryRepository,
        event_dispatcher,
        *,
        aggregate_uow: VendorAggregateUnitOfWork | None = None,
        creation_uow: VendorCreationUnitOfWork | None = None,
        authorization_port: VendorAuthorizationPort | None = None,
        idempotency_port: VendorIdempotencyPort | None = None,
        reorder_uow: PortfolioReorderUnitOfWork | None = None,
        order_allocator: PortfolioOrderAllocator | None = None,
    ):
        self.vendor_repo = vendor_repo
        self.image_repo = image_repo
        self.package_repo = package_repo
        self.inquiry_repo = inquiry_repo
        self.aggregate_uow = aggregate_uow
        self.creation_uow = creation_uow
        self.authorization_port = authorization_port
        self.idempotency_port = idempotency_port
        self.reorder_uow = reorder_uow
        self.order_allocator = order_allocator

    def create_profile(self, cmd: CreateVendorProfileCommand) -> VendorProfileDTO:
        def operation() -> VendorProfileDTO:
            existing = self.vendor_repo.get_by_user_id(cmd.actor.user_id)
            if existing:
                raise VendorConflict("User already has a vendor profile.", code="vendor_profile_exists")
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
            saved = self._add_created_with_pending_events(profile)
            return self._to_profile_dto(saved)

        return self._run_idempotent("vendor_profile.create", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

    def update_profile(self, cmd: UpdateVendorProfileCommand) -> VendorProfileDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
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
        profile.update_details(**updates)
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def submit_for_review(self, cmd: SubmitVendorForReviewCommand) -> VendorProfileDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
        original_version = profile.version
        profile.submit_for_review()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def approve_vendor(self, cmd: ApproveVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
        original_version = profile.version
        profile.approve()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def reject_vendor(self, cmd: RejectVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
        original_version = profile.version
        profile.reject(cmd.reason)
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def suspend_vendor(self, cmd: SuspendVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
        original_version = profile.version
        profile.suspend(cmd.reason)
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def reinstate_vendor(self, cmd: ReinstateVendorCommand) -> VendorProfileDTO:
        self._assert_moderator_can_moderate_vendor(cmd.moderator, cmd.vendor_id)
        profile = self._get_vendor_or_raise(cmd.vendor_id)
        self._assert_expected_version(profile.version, cmd.expected_version)
        original_version = profile.version
        profile.reinstate()
        return self._save_if_changed(profile, original_version, self._to_profile_dto)

    def add_portfolio_image(self, cmd: AddPortfolioImageCommand) -> PortfolioImageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)

        def operation() -> PortfolioImageDTO:
            profile = self.vendor_repo.get_by_id(cmd.vendor_id)
            ensure_vendor_can_add_portfolio_media(profile)
            allocator = self.order_allocator or self.image_repo
            if not hasattr(allocator, "allocate_next_order"):
                raise InvalidVendorCommand(field_errors={"order": ["Portfolio order allocation is not configured."]})
            next_order = allocator.allocate_next_order(cmd.vendor_id)
            image = PortfolioImage(
                id=uuid.uuid4(),
                vendor_id=cmd.vendor_id,
                public_id=cmd.public_id,
                secure_url=cmd.secure_url,
                caption=cmd.caption,
                order=next_order,
            )
            saved = self._add_with_pending_events(image)
            return self._to_image_dto(saved)

        return self._run_idempotent("portfolio_image.add", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

    def delete_portfolio_image(self, cmd: DeletePortfolioImageCommand) -> None:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        image = self.image_repo.get_for_vendor(cmd.vendor_id, cmd.image_id)
        if not image:
            raise VendorResourceNotFound("Image not found.")
        self._assert_expected_version(image.version, cmd.expected_version)
        original_version = image.version
        image.deactivate()
        if image.version == original_version:
            return
        self._save_with_pending_events(image, original_version)

    def reorder_portfolio_images(self, cmd: ReorderPortfolioImagesCommand) -> PageDTO[PortfolioImageDTO]:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        if self.reorder_uow is None:
            raise VendorOperationForbidden("Portfolio reorder requires a unit of work.")
        page = self.reorder_uow.list_vendor_images(cmd.vendor_id, PageRequest(limit=100, offset=0))
        image_map = {image.id: image for image in page.items}
        requested_ids = tuple(cmd.image_ids_in_order)
        self._validate_portfolio_reorder_ids(requested_ids, image_map)
        expected_versions = {item.resource_id: item.expected_version for item in cmd.expected_versions}
        if set(expected_versions) != set(requested_ids):
            raise InvalidVendorCommand(field_errors={"expected_versions": ["Expected versions must match image order."]})
        for image_id, expected_version in expected_versions.items():
            self._assert_expected_version(image_map[image_id].version, expected_version)

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
        return PageDTO(items=ordered, total=page.total, limit=page.limit, offset=page.offset, next_cursor=page.next_cursor)

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

        return self._run_idempotent("service_package.create", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

    def update_service_package(self, cmd: UpdateServicePackageCommand) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.version, cmd.expected_version)
        original_version = package.version
        package.update_details(cmd.name, cmd.description, cmd.price, cmd.currency, cmd.package_tier)
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def deactivate_package(self, cmd: DeactivateServicePackageCommand) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.version, cmd.expected_version)
        original_version = package.version
        package.deactivate()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def activate_package(self, cmd: ActivateServicePackageCommand) -> ServicePackageDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        package = self._get_package_or_raise(cmd.vendor_id, cmd.package_id)
        self._assert_expected_version(package.version, cmd.expected_version)
        original_version = package.version
        package.activate()
        return self._save_if_changed(package, original_version, self._to_package_dto)

    def send_inquiry(self, cmd: SendInquiryCommand) -> InquiryDTO:
        def operation() -> InquiryDTO:
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

        return self._run_idempotent("vendor_inquiry.send", cmd.vendor_id, cmd.idempotency_key, cmd, operation)

    def mark_inquiry_read(self, cmd: MarkInquiryReadCommand) -> InquiryDTO:
        self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
        inquiry = self.inquiry_repo.get_for_vendor(cmd.vendor_id, cmd.inquiry_id)
        if not inquiry:
            raise VendorResourceNotFound("Inquiry not found.")
        self._assert_expected_version(inquiry.version, cmd.expected_version)
        original_version = inquiry.version
        inquiry.mark_read()
        return self._save_if_changed(inquiry, original_version, self._to_inquiry_dto)

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
        if self.aggregate_uow is None:
            raise InvalidVendorCommand(field_errors={"aggregate_uow": ["Vendor aggregate unit of work is required."]})
        return self.aggregate_uow.add_with_pending_events(aggregate)

    def _add_created_with_pending_events(self, aggregate):
        if self.creation_uow is None:
            raise InvalidVendorCommand(field_errors={"creation_uow": ["Vendor creation unit of work is required."]})
        return self.creation_uow.add_with_pending_events(aggregate)

    def _save_with_pending_events(self, aggregate, expected_version: int):
        if self.aggregate_uow is None:
            raise InvalidVendorCommand(field_errors={"aggregate_uow": ["Vendor aggregate unit of work is required."]})
        return self.aggregate_uow.save_with_pending_events(aggregate, expected_version=expected_version)

    def _assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None:
        if self.authorization_port is None:
            raise InvalidVendorCommand(field_errors={"authorization_port": ["Vendor authorization is required."]})
        self.authorization_port.assert_actor_owns_vendor(actor, vendor_id)

    def _assert_moderator_can_moderate_vendor(self, moderator: ModeratorActor, vendor_id: uuid.UUID) -> None:
        if self.authorization_port is None:
            raise InvalidVendorCommand(field_errors={"authorization_port": ["Vendor authorization is required."]})
        self.authorization_port.assert_moderator_can_moderate_vendor(moderator, vendor_id)

    @staticmethod
    def _assert_expected_version(actual_version: int, expected_version: int) -> None:
        if expected_version != actual_version:
            raise VendorConflict("Vendor resource has changed.", code="vendor_version_conflict")

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
        if self.idempotency_port is None:
            raise InvalidVendorCommand(field_errors={"idempotency_key": ["Idempotency storage is required."]})
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
        payload = asdict(cmd) if is_dataclass(cmd) else dict(cmd)
        payload.pop("idempotency_key", None)
        payload = {key: value for key, value in payload.items() if value is not OMITTED}
        return json.dumps(payload, sort_keys=True, default=str)

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
            raise InvalidVendorCommand(field_errors={"read_repo": ["Vendor read port is required."]})
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

    def get_dashboard_summary(self, query: GetVendorDashboardSummaryQuery) -> dict:
        self._assert_actor_can_access_vendor(query)
        return self.read_repo.dashboard_summary(query.vendor_id)

    def get_analytics(self, query: GetVendorAnalyticsQuery) -> dict:
        self._assert_actor_can_access_vendor(query)
        return self.read_repo.analytics(query.vendor_id)

    def get_recent_activity(self, query: ListRecentVendorActivityQuery) -> PageDTO[dict]:
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
            raise InvalidVendorCommand(field_errors={"authorization_port": ["Vendor authorization is required."]})
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
