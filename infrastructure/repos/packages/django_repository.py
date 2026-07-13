import logging
import uuid
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from domain.vendors.entities import ServicePackage as DomainPackage
from domain.vendors.errors import ConcurrentVendorUpdate, VendorDomainError
from domain.vendors.interfaces import IServicePackageRepository, Page, PageRequest
from django_app.vendors.models import ServicePackage as DjangoPackage, VendorProfile as DjangoVendor
from infrastructure.repos.exceptions import RepositoryNotFoundError

logger = logging.getLogger(__name__)


class DjangoServicePackageRepository(IServicePackageRepository):
    def add(self, domain: DomainPackage) -> DomainPackage:
        vendor = self._get_vendor(domain.vendor_id)
        obj = DjangoPackage.objects.create(
            id=domain.id,
            vendor=vendor,
            name=domain.name,
            description=domain.description,
            price=domain.price,
            currency=domain.currency,
            package_tier=domain.package_tier,
            approval_status=domain.approval_status,
            rejection_reason=domain.rejection_reason,
            is_active=domain.is_active,
            is_deleted=domain.is_deleted,
            deleted_at=domain.deleted_at,
            last_approved_at=domain.last_approved_at,
            last_vendor_public_edit_at=domain.last_vendor_public_edit_at,
            next_vendor_edit_allowed_at=domain.next_vendor_edit_allowed_at,
            version=domain.version,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
        )
        return self._to_domain(obj)

    def get_by_id(self, package_id: uuid.UUID) -> Optional[DomainPackage]:
        try:
            return self._to_domain(DjangoPackage.all_objects.select_related("vendor").get(id=package_id))
        except ObjectDoesNotExist:
            return None

    def get_for_vendor(self, vendor_id: uuid.UUID, package_id: uuid.UUID) -> Optional[DomainPackage]:
        try:
            return self._to_domain(
                DjangoPackage.all_objects.select_related("vendor").get(id=package_id, vendor_id=vendor_id)
            )
        except ObjectDoesNotExist:
            return None

    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[DomainPackage]:
        page = page or PageRequest()
        queryset = DjangoPackage.all_objects.filter(vendor_id=vendor_id).order_by("-created_at", "id")
        total = queryset.count()
        objs = list(queryset[page.offset : page.offset + page.limit])
        return Page(items=[self._to_domain(o) for o in objs], total=total, limit=page.limit, offset=page.offset)

    def save(self, domain: DomainPackage, *, expected_version: int) -> DomainPackage:
        self._get_vendor(domain.vendor_id)
        with transaction.atomic():
            updated = DjangoPackage.all_objects.filter(
                id=domain.id,
                vendor_id=domain.vendor_id,
                version=expected_version,
            ).update(
                name=domain.name,
                description=domain.description,
                price=domain.price,
                currency=domain.currency,
                package_tier=domain.package_tier,
                approval_status=domain.approval_status,
                rejection_reason=domain.rejection_reason,
                is_active=domain.is_active,
                is_deleted=domain.is_deleted,
                deleted_at=domain.deleted_at,
                last_approved_at=domain.last_approved_at,
                last_vendor_public_edit_at=domain.last_vendor_public_edit_at,
                next_vendor_edit_allowed_at=domain.next_vendor_edit_allowed_at,
                version=F("version") + 1,
                updated_at=domain.updated_at,
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Service package was updated or ownership no longer matches.",
                    field_errors={"version": ["Service package was updated by another request."]},
                )
            obj = DjangoPackage.all_objects.select_related("vendor").get(
                id=domain.id,
                vendor_id=domain.vendor_id,
            )
        return self._to_domain(obj)

    def delete(self, package_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> Optional[DomainPackage]:
        with transaction.atomic():
            obj = DjangoPackage.all_objects.select_for_update().filter(id=package_id).first()
            if obj is None:
                return None
            updated = DjangoPackage.all_objects.filter(id=obj.id, version=obj.version).update(
                is_active=False,
                is_deleted=True,
                deleted_at=timezone.now(),
                deleted_by_id=deleted_by_id,
                version=F("version") + 1,
                updated_at=timezone.now(),
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Service package changed during deletion.",
                    field_errors={"version": ["Service package was updated by another request."]},
                )
            return self._to_domain(DjangoPackage.all_objects.get(id=obj.id))

    def delete_for_vendor(
        self,
        vendor_id: uuid.UUID,
        package_id: uuid.UUID,
        deleted_by_id: Optional[uuid.UUID] = None,
    ) -> Optional[DomainPackage]:
        with transaction.atomic():
            obj = DjangoPackage.all_objects.select_for_update().filter(
                id=package_id,
                vendor_id=vendor_id,
            ).first()
            if obj is None:
                return None
            updated = DjangoPackage.all_objects.filter(
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
                    "Service package changed during deletion.",
                    field_errors={"version": ["Service package was updated by another request."]},
                )
            return self._to_domain(DjangoPackage.all_objects.get(id=obj.id, vendor_id=vendor_id))

    def _get_vendor(self, vendor_id: uuid.UUID):
        try:
            return DjangoVendor.objects.get(id=vendor_id)
        except DjangoVendor.DoesNotExist as exc:
            raise RepositoryNotFoundError("Vendor not found") from exc

    def _to_domain(self, model: DjangoPackage) -> DomainPackage:
        try:
            return DomainPackage.rehydrate(
                id=model.id,
                vendor_id=model.vendor_id,
                name=model.name,
                description=model.description,
                price=model.price,
                currency=model.currency,
                package_tier=model.package_tier,
                approval_status=model.approval_status,
                rejection_reason=model.rejection_reason,
                is_active=model.is_active,
                is_deleted=model.is_deleted,
                deleted_at=model.deleted_at,
                last_approved_at=model.last_approved_at,
                last_vendor_public_edit_at=model.last_vendor_public_edit_at,
                next_vendor_edit_allowed_at=model.next_vendor_edit_allowed_at,
                version=model.version,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
        except VendorDomainError as exc:
            logger.warning(
                "ServicePackage strict hydration failed.",
                extra={
                    "package_id": str(model.id),
                    "vendor_id": str(model.vendor_id),
                    "error_code": exc.code,
                    "field_errors": exc.field_errors,
                },
            )
            raise
