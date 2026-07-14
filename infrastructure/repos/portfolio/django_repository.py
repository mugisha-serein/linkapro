import uuid
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from domain.vendors.shared.aggregate import ConcurrentVendorUpdate
from domain.vendors.portfolio.entity import PortfolioImage as DomainImage
from domain.vendors.portfolio.interfaces import IPortfolioImageRepository
from domain.vendors.shared.pagination import Page, PageRequest
from django_app.vendors.models import PortfolioImage as DjangoImage, VendorProfile as DjangoVendor
from infrastructure.repos.exceptions import RepositoryNotFoundError


class DjangoPortfolioImageRepository(IPortfolioImageRepository):
    def add(self, domain: DomainImage) -> DomainImage:
        obj = DjangoImage.objects.create(
            id=domain.id,
            vendor=self._get_vendor(domain.vendor_id),
            public_id=domain.public_id,
            secure_url=domain.secure_url,
            media_type=domain.media_type,
            caption=domain.caption,
            order=domain.order,
            upload_status=domain.upload_status,
            quality_status=domain.quality_status,
            visibility_status=domain.visibility_status,
            upload_error=domain.upload_error,
            failure_reason=domain.failure_reason,
            rejection_reason=domain.rejection_reason,
            original_filename=domain.original_filename,
            mime_type=domain.mime_type,
            file_size=domain.file_size,
            local_preview_url=domain.local_preview_url,
            cloudinary_public_id=domain.cloudinary_public_id,
            cloudinary_secure_url=domain.cloudinary_secure_url,
            width=domain.width,
            height=domain.height,
            duration_seconds=domain.duration_seconds,
            analyzer_score=domain.analyzer_score,
            analyzer_summary=domain.analyzer_summary,
            is_active=domain.is_active,
            is_deleted=domain.is_deleted,
            deleted_at=domain.deleted_at,
            version=domain.version,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
        return self._to_domain(obj)

    def get_by_id(self, image_id: uuid.UUID) -> Optional[DomainImage]:
        try:
            return self._to_domain(DjangoImage.all_objects.select_related("vendor").get(id=image_id))
        except ObjectDoesNotExist:
            return None

    def get_for_vendor(self, vendor_id: uuid.UUID, image_id: uuid.UUID) -> Optional[DomainImage]:
        try:
            return self._to_domain(
                DjangoImage.all_objects.select_related("vendor").get(id=image_id, vendor_id=vendor_id)
            )
        except ObjectDoesNotExist:
            return None

    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[DomainImage]:
        page = page or PageRequest()
        queryset = DjangoImage.all_objects.filter(vendor_id=vendor_id).order_by("order", "id")
        total = queryset.count()
        objs = list(queryset[page.offset : page.offset + page.limit])
        return Page(items=[self._to_domain(o) for o in objs], total=total, limit=page.limit, offset=page.offset)

    def save(self, domain: DomainImage, *, expected_version: int) -> DomainImage:
        self._get_vendor(domain.vendor_id)
        with transaction.atomic():
            updated = DjangoImage.all_objects.filter(
                id=domain.id,
                vendor_id=domain.vendor_id,
                version=expected_version,
            ).update(
                public_id=domain.public_id,
                secure_url=domain.secure_url,
                media_type=domain.media_type,
                caption=domain.caption,
                order=domain.order,
                upload_status=domain.upload_status,
                quality_status=domain.quality_status,
                visibility_status=domain.visibility_status,
                upload_error=domain.upload_error,
                failure_reason=domain.failure_reason,
                rejection_reason=domain.rejection_reason,
                original_filename=domain.original_filename,
                mime_type=domain.mime_type,
                file_size=domain.file_size,
                local_preview_url=domain.local_preview_url,
                cloudinary_public_id=domain.cloudinary_public_id,
                cloudinary_secure_url=domain.cloudinary_secure_url,
                width=domain.width,
                height=domain.height,
                duration_seconds=domain.duration_seconds,
                analyzer_score=domain.analyzer_score,
                analyzer_summary=domain.analyzer_summary,
                is_active=domain.is_active,
                is_deleted=domain.is_deleted,
                deleted_at=domain.deleted_at,
                version=F("version") + 1,
                updated_at=domain.updated_at,
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Portfolio item was updated or ownership no longer matches.",
                    field_errors={"version": ["Portfolio item was updated by another request."]},
                )
            obj = DjangoImage.all_objects.select_related("vendor").get(
                id=domain.id,
                vendor_id=domain.vendor_id,
            )
        return self._to_domain(obj)

    def delete(self, image_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None:
        with transaction.atomic():
            obj = DjangoImage.all_objects.select_for_update().filter(id=image_id).first()
            if obj is None:
                return
            updated = DjangoImage.all_objects.filter(id=obj.id, version=obj.version).update(
                is_active=False,
                is_deleted=True,
                deleted_at=timezone.now(),
                deleted_by_id=deleted_by_id,
                version=F("version") + 1,
                updated_at=timezone.now(),
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Portfolio item changed during deletion.",
                    field_errors={"version": ["Portfolio item was updated by another request."]},
                )

    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        image_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> None:
        with transaction.atomic():
            obj = DjangoImage.all_objects.select_for_update().filter(
                id=image_id,
                vendor_id=vendor_id,
            ).first()
            if obj is None:
                return
            updated = DjangoImage.all_objects.filter(
                id=obj.id,
                vendor_id=vendor_id,
                version=obj.version,
            ).update(
                is_active=False,
                is_deleted=True,
                deleted_at=timezone.now(),
                deleted_by_id=deleted_by_id,
                version=F("version") + 1,
                updated_at=timezone.now(),
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Portfolio item changed during deletion.",
                    field_errors={"version": ["Portfolio item was updated by another request."]},
                )

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
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
