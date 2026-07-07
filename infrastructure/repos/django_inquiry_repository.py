import uuid
from typing import Optional, List
from django.core.exceptions import ObjectDoesNotExist

from domain.vendors.entities import Inquiry as DomainInquiry
from domain.vendors.interfaces import IInquiryRepository
from django_app.vendors.models import Inquiry as DjangoInquiry, VendorProfile as DjangoVendor
from infrastructure.repos.exceptions import RepositoryNotFoundError


class DjangoInquiryRepository(IInquiryRepository):
    def add(self, domain: DomainInquiry) -> DomainInquiry:
        return self.save(domain)

    def get_by_id(self, inquiry_id: uuid.UUID) -> Optional[DomainInquiry]:
        try:
            obj = DjangoInquiry.objects.select_related("vendor").get(id=inquiry_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def get_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> Optional[DomainInquiry]:
        try:
            obj = DjangoInquiry.objects.select_related("vendor").get(id=inquiry_id, vendor_id=vendor_id)
            return self._to_domain(obj)
        except ObjectDoesNotExist:
            return None

    def list_by_vendor(self, vendor_id: uuid.UUID) -> List[DomainInquiry]:
        objs = DjangoInquiry.objects.filter(vendor_id=vendor_id).order_by("-created_at")
        return [self._to_domain(o) for o in objs]

    def save(self, domain: DomainInquiry) -> DomainInquiry:
        try:
            obj = DjangoInquiry.objects.get(id=domain.id)
        except DjangoInquiry.DoesNotExist:
            obj = DjangoInquiry(id=domain.id)

        obj.vendor = self._get_vendor(domain.vendor_id)
        obj.client_name = domain.client_name
        obj.client_email = domain.client_email
        obj.client_phone = domain.client_phone
        obj.message = domain.message
        obj.event_date = domain.event_date
        obj.is_read = domain.is_read
        obj.save()
        return self._to_domain(obj)

    def delete(self, inquiry_id: uuid.UUID) -> None:
        DjangoInquiry.objects.filter(id=inquiry_id).delete()

    def delete_for_vendor(self, vendor_id: uuid.UUID, inquiry_id: uuid.UUID) -> None:
        DjangoInquiry.objects.filter(id=inquiry_id, vendor_id=vendor_id).delete()

    def _get_vendor(self, vendor_id: uuid.UUID):
        try:
            return DjangoVendor.objects.get(id=vendor_id)
        except DjangoVendor.DoesNotExist as exc:
            raise RepositoryNotFoundError("Vendor not found") from exc

    def _to_domain(self, model: DjangoInquiry) -> DomainInquiry:
        return DomainInquiry(
            id=model.id,
            vendor_id=model.vendor_id,
            client_name=model.client_name,
            client_email=model.client_email,
            client_phone=model.client_phone,
            message=model.message,
            event_date=model.event_date,
            is_read=model.is_read,
            created_at=model.created_at,
        )
