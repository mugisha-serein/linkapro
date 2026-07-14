import uuid
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F

from domain.vendors.shared.aggregate import ConcurrentVendorUpdate
from domain.vendors.inquiries.entity import Inquiry as DomainInquiry
from domain.vendors.inquiries.interfaces import IInquiryRepository
from domain.vendors.shared.pagination import Page, PageRequest
from django_app.vendors.models import Inquiry as DjangoInquiry, VendorProfile as DjangoVendor
from infrastructure.repos.exceptions import RepositoryNotFoundError


class DjangoInquiryRepository(IInquiryRepository):
    def add(self, domain: DomainInquiry) -> DomainInquiry:
        obj = DjangoInquiry.objects.create(
            id=domain.id,
            vendor=self._get_vendor(domain.vendor_id),
            client_name=domain.client_name,
            client_email=domain.client_email,
            client_phone=domain.client_phone,
            message=domain.message,
            event_date=domain.event_date,
            is_read=domain.is_read,
            version=domain.version,
            created_at=domain.created_at,
        )
        return self._to_domain(obj)

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

    def list_by_vendor(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[DomainInquiry]:
        page = page or PageRequest()
        queryset = DjangoInquiry.objects.filter(vendor_id=vendor_id).order_by("-created_at", "id")
        total = queryset.count()
        objs = list(queryset[page.offset : page.offset + page.limit])
        return Page(items=[self._to_domain(o) for o in objs], total=total, limit=page.limit, offset=page.offset)

    def save(self, domain: DomainInquiry, *, expected_version: int) -> DomainInquiry:
        self._get_vendor(domain.vendor_id)
        with transaction.atomic():
            updated = DjangoInquiry.objects.filter(
                id=domain.id,
                vendor_id=domain.vendor_id,
                version=expected_version,
            ).update(
                client_name=domain.client_name,
                client_email=domain.client_email,
                client_phone=domain.client_phone,
                message=domain.message,
                event_date=domain.event_date,
                is_read=domain.is_read,
                version=F("version") + 1,
            )
            if updated != 1:
                raise ConcurrentVendorUpdate(
                    "Inquiry was updated or ownership no longer matches.",
                    field_errors={"version": ["Inquiry was updated by another request."]},
                )
            obj = DjangoInquiry.objects.select_related("vendor").get(
                id=domain.id,
                vendor_id=domain.vendor_id,
            )
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
            version=model.version,
            created_at=model.created_at,
        )
