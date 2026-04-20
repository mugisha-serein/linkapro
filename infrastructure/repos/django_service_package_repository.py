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
            obj = DjangoPackage.objects.get(id=domain.id)
        except DjangoPackage.DoesNotExist:
            obj = DjangoPackage(id=domain.id)

        obj.vendor = DjangoVendor.objects.get(id=domain.vendor_id)
        obj.name = domain.name
        obj.description = domain.description
        obj.price = domain.price
        obj.currency = domain.currency
        obj.is_active = domain.is_active
        obj.save()
        return self._to_domain(obj)

    def delete(self, package_id: uuid.UUID) -> None:
        DjangoPackage.objects.filter(id=package_id).delete()

    def _to_domain(self, model: DjangoPackage) -> DomainPackage:
        return DomainPackage(
            id=model.id,
            vendor_id=model.vendor_id,
            name=model.name,
            description=model.description,
            price=float(model.price),
            currency=model.currency,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )