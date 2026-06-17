import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.vendors.entities import PortfolioImage as DomainImage
from domain.vendors.interfaces import IPortfolioImageRepository
from django_app.vendors.models import PortfolioImage as DjangoImage, VendorProfile as DjangoVendor


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
            obj = DjangoImage.objects.get(id=domain.id)
        except DjangoImage.DoesNotExist:
            obj = DjangoImage(id=domain.id)

        obj.vendor = DjangoVendor.objects.get(id=domain.vendor_id)
        obj.public_id = domain.public_id
        obj.secure_url = domain.secure_url
        obj.caption = domain.caption
        obj.order = domain.order
        obj.upload_status = domain.upload_status
        obj.upload_error = domain.upload_error
        obj.original_filename = domain.original_filename
        obj.save()
        return self._to_domain(obj)

    def delete(self, image_id: uuid.UUID) -> None:
        DjangoImage.objects.filter(id=image_id).delete()

    def _to_domain(self, model: DjangoImage) -> DomainImage:
        return DomainImage(
            id=model.id,
            vendor_id=model.vendor_id,
            public_id=model.public_id,
            secure_url=model.secure_url,
            caption=model.caption,
            order=model.order,
            upload_status=model.upload_status,
            upload_error=model.upload_error,
            original_filename=model.original_filename,
            created_at=model.created_at,
        )
