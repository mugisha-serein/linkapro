import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.vendors.entities import ServicePackage as DomainPackage
from domain.vendors.interfaces import IServicePackageRepository
from django_app.vendors.models import ServicePackage as DjangoPackage, VendorProfile as DjangoVendor


class DjangoServicePackageRepository(IServicePackageRepository):
    def get_by_id(self, package_id: uuid.UUID) -> Optional[DomainPackage]:
        try:
            obj = DjangoPackage.objects.select_related("vendor").get(id=package_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_vendor(self, vendor_id: uuid.UUID) -> List[DomainPackage]:
        objs = DjangoPackage.objects.filter(vendor_id=vendor_id)
        return [self._to_domain(o) for o in objs]

    def save(self, domain: DomainPackage) -> DomainPackage:
        try:
            obj = DjangoPackage.all_objects.get(id=domain.id)
        except DjangoPackage.DoesNotExist:
            obj = DjangoPackage(id=domain.id)

        obj.vendor = DjangoVendor.objects.get(id=domain.vendor_id)
        obj.name = domain.name
        obj.description = domain.description
        obj.price = domain.price
        obj.currency = domain.currency
        obj.package_tier = domain.package_tier
        obj.approval_status = domain.approval_status
        obj.rejection_reason = domain.rejection_reason
        obj.is_active = domain.is_active
        obj.is_deleted = domain.is_deleted
        obj.deleted_at = domain.deleted_at
        obj.save()
        return self._to_domain(obj)

    def delete(self, package_id: uuid.UUID, deleted_by_id: Optional[uuid.UUID] = None) -> None:
        try:
            obj = DjangoPackage.all_objects.get(id=package_id)
        except DjangoPackage.DoesNotExist:
            return
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])
        obj.soft_delete(user_id=deleted_by_id)

    def _to_domain(self, model: DjangoPackage) -> DomainPackage:
        return DomainPackage(
            id=model.id,
            vendor_id=model.vendor_id,
            name=model.name,
            description=model.description,
            # Preserve Django DecimalField values exactly. The domain layer owns money as Decimal;
            # turning this into float would reintroduce rounding drift after persistence.
            price=model.price,
            currency=model.currency,
            package_tier=model.package_tier,
            approval_status=model.approval_status,
            rejection_reason=model.rejection_reason,
            is_active=model.is_active,
            is_deleted=model.is_deleted,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
