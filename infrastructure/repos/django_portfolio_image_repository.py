import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from domain.vendors.entities import PortfolioImage as DomainImage
from domain.vendors.interfaces import IPortfolioImageRepository
from django_app.vendors.models import PortfolioImage as DjangoImage, VendorProfile as DjangoVendor
from infrastructure.repos.exceptions import RepositoryNotFoundError


class DjangoPortfolioImageRepository(IPortfolioImageRepository):
    def get_by_id(self, image_id: uuid.UUID) -> Optional[DomainImage]:
        try:
            obj = DjangoImage.objects.select_related("vendor").get(id=image_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_vendor(self, vendor_id: uuid.UUID) -> List[DomainImage]:
        objs = DjangoImage.objects.filter(vendor_id=vendor_id).order_by("order")
        return [self._to_domain(o) for o in objs]

    def save(self, domain: DomainImage) -> DomainImage:
        try:
            obj = DjangoImage.all_objects.get(id=domain.id)
        except DjangoImage.DoesNotExist:
            obj = DjangoImage(id=domain.id)

        obj.vendor = self._get_vendor(domain.vendor_id)
        obj.public_id = domain.public_id
        obj.secure_url = domain.secure_url
        obj.media_type = domain.media_type
        obj.caption = domain.caption
        obj.order = domain.order
        obj.upload_status = domain.upload_status
        obj.quality_status = domain.quality_status
        obj.visibility_status = domain.visibility_status
        obj.upload_error = domain.upload_error
        obj.failure_reason = domain.failure_reason
        obj.rejection_reason = domain.rejection_reason
        obj.original_filename = domain.original_filename
        obj.mime_type = domain.mime_type
        obj.file_size = domain.file_size
        obj.local_preview_url = domain.local_preview_url
        obj.cloudinary_public_id = domain.cloudinary_public_id
        obj.cloudinary_secure_url = domain.cloudinary_secure_url
        obj.width = domain.width
        obj.height = domain.height
        obj.duration_seconds = domain.duration_seconds
        obj.analyzer_score = domain.analyzer_score
        obj.analyzer_summary = domain.analyzer_summary
        obj.is_active = domain.is_active
        obj.is_deleted = domain.is_deleted
        obj.deleted_at = domain.deleted_at
        obj.save()
        return self._to_domain(obj)

    def delete(self, image_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None:
        try:
            obj = DjangoImage.all_objects.get(id=image_id)
        except DjangoImage.DoesNotExist:
            return

        obj.is_active = False
        obj.is_deleted = True
        obj.deleted_at = timezone.now()
        obj.deleted_by_id = deleted_by_id
        obj.save(update_fields=["is_active", "is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def _get_vendor(self, vendor_id: uuid.UUID):
        try:
            return DjangoVendor.objects.get(id=vendor_id)
        except DjangoVendor.DoesNotExist as exc:
            raise RepositoryNotFoundError("Vendor not found") from exc

    def _to_domain(self, model: DjangoImage) -> DomainImage:
        return DomainImage(
            id=model.id,
            vendor_id=model.vendor_id,
            public_id=model.public_id,
            secure_url=model.secure_url,
            caption=model.caption,
            order=model.order,
            media_type=model.media_type,
            upload_status=model.upload_status,
            quality_status=model.quality_status,
            visibility_status=model.visibility_status,
            upload_error=model.upload_error,
            failure_reason=model.failure_reason,
            rejection_reason=model.rejection_reason,
            original_filename=model.original_filename,
            mime_type=model.mime_type,
            file_size=model.file_size,
            local_preview_url=model.local_preview_url,
            cloudinary_public_id=model.cloudinary_public_id,
            cloudinary_secure_url=model.cloudinary_secure_url,
            width=model.width,
            height=model.height,
            duration_seconds=model.duration_seconds,
            analyzer_score=model.analyzer_score,
            analyzer_summary=model.analyzer_summary,
            is_active=model.is_active,
            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
