from __future__ import annotations

from domain.vendors.inquiries.entity import Inquiry
from domain.vendors.packages.entity import ServicePackage
from domain.vendors.portfolio.entity import PortfolioImage
from domain.vendors.profile.entity import VendorProfile
from application.vendors.inquiries.dtos import InquiryDTO
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.profile.dtos import VendorProfileDTO


class VendorDTOMapperMixin:
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
