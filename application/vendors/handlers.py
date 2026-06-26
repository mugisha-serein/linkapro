import uuid
from typing import Optional, List

from domain.shared.utils import utc_now
from domain.vendors.entities import (
    VendorProfile, PortfolioImage, ServicePackage, Inquiry,
    VendorStatus, ServiceCategory
)
from domain.vendors.inquiry_policy import ensure_vendor_can_receive_inquiry
from domain.vendors.package_rules import validate_service_package_rules
from domain.vendors.interfaces import (
    IVendorProfileRepository, IPortfolioImageRepository,
    IServicePackageRepository, IInquiryRepository
)
from domain.vendors.events import (
    VendorSubmittedForReview, VendorApproved, VendorRejected,
    VendorSuspended, InquiryReceived
)
from .commands import *
from .dtos import *


class VendorCommandHandlers:
    def __init__(
        self,
        vendor_repo: IVendorProfileRepository,
        image_repo: IPortfolioImageRepository,
        package_repo: IServicePackageRepository,
        inquiry_repo: IInquiryRepository,
        event_dispatcher,
    ):
        self.vendor_repo = vendor_repo
        self.image_repo = image_repo
        self.package_repo = package_repo
        self.inquiry_repo = inquiry_repo
        self.event_dispatcher = event_dispatcher

    def create_profile(self, cmd: CreateVendorProfileCommand) -> VendorProfileDTO:
        existing = self.vendor_repo.get_by_user_id(cmd.user_id)
        if existing:
            raise ValueError("User already has a vendor profile")
        profile = VendorProfile(
            id=uuid.uuid4(),
            user_id=cmd.user_id,
            business_name=cmd.business_name,
            category=ServiceCategory(cmd.category),
            description=cmd.description,
            service_area=cmd.service_area,
            contact_email=cmd.contact_email,
            contact_phone=cmd.contact_phone,
            custom_category=cmd.custom_category,
            website=cmd.website,
        )
        saved = self.vendor_repo.save(profile)
        return self._to_profile_dto(saved)

    def update_profile(self, cmd: UpdateVendorProfileCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        if cmd.business_name: profile.business_name = cmd.business_name
        if cmd.category: profile.category = ServiceCategory(cmd.category)
        if cmd.description: profile.description = cmd.description
        if cmd.service_area: profile.service_area = cmd.service_area
        if cmd.contact_email: profile.contact_email = cmd.contact_email
        if cmd.contact_phone: profile.contact_phone = cmd.contact_phone
        if cmd.custom_category is not None: profile.custom_category = cmd.custom_category
        if cmd.website is not None: profile.website = cmd.website
        saved = self.vendor_repo.save(profile)
        return self._to_profile_dto(saved)

    def submit_for_review(self, cmd: SubmitVendorForReviewCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        profile.submit_for_review()
        saved = self.vendor_repo.save(profile)
        self.event_dispatcher.dispatch(
            VendorSubmittedForReview(vendor_id=saved.id, user_id=saved.user_id, occurred_at=utc_now())
        )
        return self._to_profile_dto(saved)

    def approve_vendor(self, cmd: ApproveVendorCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        profile.approve()
        saved = self.vendor_repo.save(profile)
        self.event_dispatcher.dispatch(VendorApproved(vendor_id=saved.id, occurred_at=utc_now()))
        return self._to_profile_dto(saved)

    def reject_vendor(self, cmd: RejectVendorCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        profile.reject(cmd.reason)
        saved = self.vendor_repo.save(profile)
        self.event_dispatcher.dispatch(
            VendorRejected(vendor_id=saved.id, reason=cmd.reason, occurred_at=utc_now())
        )
        return self._to_profile_dto(saved)

    def suspend_vendor(self, cmd: SuspendVendorCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        profile.suspend()
        saved = self.vendor_repo.save(profile)
        self.event_dispatcher.dispatch(VendorSuspended(vendor_id=saved.id, occurred_at=utc_now()))
        return self._to_profile_dto(saved)

    def reinstate_vendor(self, cmd: ReinstateVendorCommand) -> VendorProfileDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        if not profile:
            raise ValueError("Vendor not found")
        profile.reinstate()
        saved = self.vendor_repo.save(profile)
        return self._to_profile_dto(saved)

    def add_portfolio_image(self, cmd: AddPortfolioImageCommand) -> PortfolioImageDTO:
        images = self.image_repo.list_by_vendor(cmd.vendor_id)
        max_order = max([i.order for i in images], default=-1)
        image = PortfolioImage(
            id=uuid.uuid4(),
            vendor_id=cmd.vendor_id,
            public_id=cmd.public_id,
            secure_url=cmd.secure_url,
            caption=cmd.caption,
            order=max_order + 1,
        )
        saved = self.image_repo.save(image)
        return self._to_image_dto(saved)

    def delete_portfolio_image(self, cmd: DeletePortfolioImageCommand) -> None:
        image = self.image_repo.get_by_id(cmd.image_id)
        self._assert_image_owned(image, cmd.vendor_id)
        self.image_repo.delete(cmd.image_id, deleted_by_id=cmd.deleted_by_id)

    def reorder_portfolio_images(self, cmd: ReorderPortfolioImagesCommand) -> List[PortfolioImageDTO]:
        images = self.image_repo.list_by_vendor(cmd.vendor_id)
        image_map = {img.id: img for img in images}
        requested_ids = list(cmd.image_ids_in_order)
        self._validate_portfolio_reorder_ids(requested_ids, image_map)

        reordered = []
        for idx, img_id in enumerate(requested_ids):
            img = image_map[img_id]
            img.reorder(idx)
            saved = self.image_repo.save(img)
            reordered.append(self._to_image_dto(saved))
        return reordered

    def create_service_package(self, cmd: CreateServicePackageCommand) -> ServicePackageDTO:
        package = ServicePackage(
            id=uuid.uuid4(),
            vendor_id=cmd.vendor_id,
            name=cmd.name,
            description=cmd.description,
            price=cmd.price,
            currency=cmd.currency,
            package_tier=cmd.package_tier,
            approval_status="waiting_approval",
            is_active=False,
        )
        validate_service_package_rules(
            name=package.name,
            description=package.description,
            price=package.price,
            package_tier=package.package_tier,
        )
        saved = self.package_repo.save(package)
        return self._to_package_dto(saved)

    def update_service_package(self, cmd: UpdateServicePackageCommand) -> ServicePackageDTO:
        package = self.package_repo.get_by_id(cmd.package_id)
        self._assert_package_owned(package, cmd.vendor_id)
        package.update_details(cmd.name, cmd.description, cmd.price, cmd.currency, cmd.package_tier)
        validate_service_package_rules(
            name=package.name,
            description=package.description,
            price=package.price,
            package_tier=package.package_tier,
        )
        saved = self.package_repo.save(package)
        return self._to_package_dto(saved)

    def deactivate_package(self, cmd: DeactivateServicePackageCommand) -> ServicePackageDTO:
        package = self.package_repo.get_by_id(cmd.package_id)
        self._assert_package_owned(package, cmd.vendor_id)
        package.deactivate()
        self.package_repo.save(package)
        self.package_repo.delete(cmd.package_id, deleted_by_id=cmd.deleted_by_id)
        return self._to_package_dto(package)

    def activate_package(self, cmd: ActivateServicePackageCommand) -> ServicePackageDTO:
        package = self.package_repo.get_by_id(cmd.package_id)
        self._assert_package_owned(package, cmd.vendor_id)
        package.activate()
        saved = self.package_repo.save(package)
        return self._to_package_dto(saved)

    def send_inquiry(self, cmd: SendInquiryCommand) -> InquiryDTO:
        profile = self.vendor_repo.get_by_id(cmd.vendor_id)
        ensure_vendor_can_receive_inquiry(profile)
        inquiry = Inquiry(
            id=uuid.uuid4(),
            vendor_id=cmd.vendor_id,
            client_name=cmd.client_name,
            client_email=cmd.client_email,
            client_phone=cmd.client_phone,
            message=cmd.message,
            event_date=cmd.event_date,
        )
        saved = self.inquiry_repo.save(inquiry)
        self.event_dispatcher.dispatch(
            InquiryReceived(inquiry_id=saved.id, vendor_id=saved.vendor_id, occurred_at=utc_now())
        )
        return self._to_inquiry_dto(saved)

    @staticmethod
    def _validate_portfolio_reorder_ids(requested_ids: List[uuid.UUID], image_map: dict[uuid.UUID, PortfolioImage]) -> None:
        if not requested_ids:
            raise ValueError("Portfolio image order is required")
        if len(requested_ids) != len(set(requested_ids)):
            raise ValueError("Portfolio image order contains duplicate images")
        if set(requested_ids) != set(image_map.keys()):
            raise ValueError("Portfolio image order must include every image belonging to this vendor")

    @staticmethod
    def _assert_package_owned(package: ServicePackage | None, vendor_id: uuid.UUID | None) -> None:
        if not package or (vendor_id is not None and package.vendor_id != vendor_id):
            raise ValueError("Package not found")

    @staticmethod
    def _assert_image_owned(image: PortfolioImage | None, vendor_id: uuid.UUID | None) -> None:
        if not image or (vendor_id is not None and image.vendor_id != vendor_id):
            raise ValueError("Image not found")

    # DTO conversion static methods
    @staticmethod
    def _to_profile_dto(p: VendorProfile) -> VendorProfileDTO:
        return VendorProfileDTO(
            id=p.id, user_id=p.user_id, business_name=p.business_name, category=p.category.value,
            description=p.description, service_area=p.service_area, contact_email=p.contact_email,
            contact_phone=p.contact_phone, custom_category=p.custom_category, website=p.website, status=p.status.value,
            submitted_at=p.submitted_at, approved_at=p.approved_at, rejected_at=p.rejected_at,
            rejection_reason=p.rejection_reason
        )

    @staticmethod
    def _to_image_dto(i: PortfolioImage) -> PortfolioImageDTO:
        return PortfolioImageDTO(id=i.id, vendor_id=i.vendor_id, secure_url=i.secure_url,
                                 caption=i.caption, order=i.order,
                                 media_type=i.media_type,
                                 upload_status=i.upload_status,
                                 quality_status=i.quality_status,
                                 visibility_status=i.visibility_status,
                                 upload_error=i.upload_error,
                                 failure_reason=i.failure_reason,
                                 rejection_reason=i.rejection_reason,
                                 original_filename=i.original_filename,
                                 mime_type=i.mime_type,
                                 file_size=i.file_size,
                                 local_preview_url=i.local_preview_url,
                                 cloudinary_public_id=i.cloudinary_public_id,
                                 cloudinary_secure_url=i.cloudinary_secure_url,
                                 width=i.width,
                                 height=i.height,
                                 duration_seconds=i.duration_seconds,
                                 analyzer_score=i.analyzer_score,
                                 analyzer_summary=i.analyzer_summary,
                                 is_active=i.is_active,
                                 is_deleted=i.is_deleted,
                                 deleted_at=i.deleted_at)

    @staticmethod
    def _to_package_dto(p: ServicePackage) -> ServicePackageDTO:
        return ServicePackageDTO(id=p.id, vendor_id=p.vendor_id, name=p.name,
                                 description=p.description, price=p.price, currency=p.currency,
                                 package_tier=p.package_tier, approval_status=p.approval_status,
                                 rejection_reason=p.rejection_reason, is_active=p.is_active,
                                 is_deleted=p.is_deleted, deleted_at=p.deleted_at)

    @staticmethod
    def _to_inquiry_dto(i: Inquiry) -> InquiryDTO:
        return InquiryDTO(id=i.id, vendor_id=i.vendor_id, client_name=i.client_name,
                          client_email=i.client_email, client_phone=i.client_phone,
                          message=i.message, event_date=i.event_date, is_read=i.is_read,
                          created_at=i.created_at)


class VendorQueryHandlers:
    def __init__(self, vendor_repo: IVendorProfileRepository,
                 image_repo: IPortfolioImageRepository,
                 package_repo: IServicePackageRepository,
                 inquiry_repo: IInquiryRepository):
        self.vendor_repo = vendor_repo
        self.image_repo = image_repo
        self.package_repo = package_repo
        self.inquiry_repo = inquiry_repo

    def get_vendor(self, vendor_id: uuid.UUID) -> Optional[VendorProfileDTO]:
        p = self.vendor_repo.get_by_id(vendor_id)
        return VendorCommandHandlers._to_profile_dto(p) if p else None

    def get_vendor_by_user(self, user_id: uuid.UUID) -> Optional[VendorProfileDTO]:
        p = self.vendor_repo.get_by_user_id(user_id)
        return VendorCommandHandlers._to_profile_dto(p) if p else None

    def list_pending_approvals(self) -> List[VendorProfileDTO]:
        profiles = self.vendor_repo.list_by_status(VendorStatus.PENDING_REVIEW)
        return [VendorCommandHandlers._to_profile_dto(p) for p in profiles]

    def list_portfolio_images(self, vendor_id: uuid.UUID) -> List[PortfolioImageDTO]:
        images = self.image_repo.list_by_vendor(vendor_id)
        return [VendorCommandHandlers._to_image_dto(i) for i in images]

    def list_service_packages(self, vendor_id: uuid.UUID) -> List[ServicePackageDTO]:
        packages = self.package_repo.list_by_vendor(vendor_id)
        return [VendorCommandHandlers._to_package_dto(p) for p in packages]

    def list_inquiries(self, vendor_id: uuid.UUID) -> List[InquiryDTO]:
        inquiries = self.inquiry_repo.list_by_vendor(vendor_id)
        return [VendorCommandHandlers._to_inquiry_dto(i) for i in inquiries]

    def get_dashboard_summary(self, vendor_id: uuid.UUID) -> dict:
        metrics = self._vendor_metrics(vendor_id)
        return {
            "profile_score": metrics["profile_completion"],
            "total_views": 0,
            "planner_requests": metrics["total_inquiries"],
            "unread_inquiries": metrics["unread_inquiries"],
            "active_packages": metrics["active_packages"],
            "portfolio_count": metrics["portfolio_count"],
            "account_status": metrics["account_status"],
            "total_packages": metrics["total_packages"],
            "pending_packages": metrics["pending_packages"],
        }

    def get_analytics(self, vendor_id: uuid.UUID) -> dict:
        metrics = self._vendor_metrics(vendor_id)
        return {
            "total_views": 0,
            "views_trend": 0,
            "total_inquiries": metrics["total_inquiries"],
            "inquiries_mtd": metrics["inquiries_mtd"],
            "unresponded_inquiries": metrics["unread_inquiries"],
            "avg_response_time_hours": None,
            "conversion_rate": None,
            "earnings_mtd": "0",
            "pending_payments": "0",
            "profile_completion": metrics["profile_completion"],
            "active_packages": metrics["active_packages"],
            "portfolio_count": metrics["portfolio_count"],
            "account_status": metrics["account_status"],
            "service_area": metrics["service_area"],
            "total_packages": metrics["total_packages"],
            "pending_packages": metrics["pending_packages"],
            "approved_packages": metrics["approved_packages"],
            "rejected_packages": metrics["rejected_packages"],
            "read_inquiries": metrics["read_inquiries"],
            "response_rate": metrics["response_rate"],
            "unavailable_metrics": [
                "total_views",
                "views_trend",
                "avg_response_time_hours",
                "conversion_rate",
                "earnings_mtd",
                "pending_payments",
            ],
        }

    def get_recent_activity(self, vendor_id: uuid.UUID, limit: int = 10) -> List[dict]:
        inquiries = sorted(
            self.inquiry_repo.list_by_vendor(vendor_id),
            key=lambda inquiry: inquiry.created_at,
            reverse=True,
        )[:limit]

        activity = []
        for inquiry in inquiries:
            activity.append(
                {
                    "id": str(inquiry.id),
                    "type": "inquiry_received",
                    "title": f"New inquiry from {inquiry.client_name}",
                    "description": inquiry.message[:120],
                    "timestamp": inquiry.created_at.isoformat(),
                    "metadata": {"is_read": inquiry.is_read},
                }
            )
        return activity

    def _vendor_metrics(self, vendor_id: uuid.UUID) -> dict:
        profile = self.vendor_repo.get_by_id(vendor_id)
        inquiries = self.inquiry_repo.list_by_vendor(vendor_id)
        packages = self.package_repo.list_by_vendor(vendor_id)
        images = self.image_repo.list_by_vendor(vendor_id)
        now = utc_now()

        total_inquiries = len(inquiries)
        unread_inquiries = sum(1 for inquiry in inquiries if not inquiry.is_read)
        read_inquiries = total_inquiries - unread_inquiries
        inquiries_mtd = sum(
            1
            for inquiry in inquiries
            if inquiry.created_at and inquiry.created_at.year == now.year and inquiry.created_at.month == now.month
        )
        active_packages = sum(
            1 for package in packages if package.is_active and package.approval_status == "approved"
        )
        approved_packages = sum(1 for package in packages if package.approval_status == "approved")
        pending_packages = sum(1 for package in packages if package.approval_status == "waiting_approval")
        rejected_packages = sum(1 for package in packages if package.approval_status == "rejected")
        response_rate = round((read_inquiries / total_inquiries) * 100) if total_inquiries else 0

        return {
            "profile_completion": self._profile_completion_score(profile, images, packages),
            "total_inquiries": total_inquiries,
            "inquiries_mtd": inquiries_mtd,
            "unread_inquiries": unread_inquiries,
            "read_inquiries": read_inquiries,
            "response_rate": response_rate,
            "total_packages": len(packages),
            "active_packages": active_packages,
            "approved_packages": approved_packages,
            "pending_packages": pending_packages,
            "rejected_packages": rejected_packages,
            "portfolio_count": len(images),
            "account_status": profile.status.value if profile else "draft",
            "service_area": profile.service_area if profile else "",
        }

    @staticmethod
    def _profile_completion_score(profile, images, packages) -> int:
        if not profile:
            return 0
        fields = [
            profile.business_name,
            profile.description,
            profile.service_area,
            profile.contact_email,
            profile.contact_phone,
        ]
        filled = sum(1 for value in fields if value)
        if images:
            filled += 1
        if packages:
            filled += 1
        total = len(fields) + 2
        return round((filled / total) * 100)
