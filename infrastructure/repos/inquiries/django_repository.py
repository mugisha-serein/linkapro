import uuid
from datetime import date, datetime, time
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from domain.vendors.shared.aggregate import ConcurrentVendorUpdate
from domain.vendors.inquiries.entity import Inquiry as DomainInquiry
from domain.vendors.inquiries.interfaces import InquiryDateRange
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
        return self._page_queryset(queryset, page)

    def search(
        self,
        vendor_id: uuid.UUID,
        query: str | None,
        status_filter: str | None,
        date_range: InquiryDateRange | None,
        page: PageRequest | None = None,
    ) -> Page[DomainInquiry]:
        page = page or PageRequest()
        queryset = DjangoInquiry.objects.filter(vendor_id=vendor_id)
        search_text = (query or "").strip()
        if search_text:
            queryset = queryset.filter(
                Q(client_name__icontains=search_text)
                | Q(client_email__icontains=search_text)
                | Q(client_phone__icontains=search_text)
                | Q(message__icontains=search_text)
            )
        status = (status_filter or "").strip().lower()
        if status == "unread":
            queryset = queryset.filter(is_read=False)
        elif status in {"read", "read_unanswered"}:
            queryset = queryset.filter(is_read=True)
        elif status == "answered":
            queryset = queryset.none()
        if date_range is not None:
            start, end = date_range
            if start is not None:
                queryset = queryset.filter(created_at__gte=self._date_range_boundary(start, end_of_day=False))
            if end is not None:
                queryset = queryset.filter(created_at__lte=self._date_range_boundary(end, end_of_day=True))
        return self._page_queryset(queryset.order_by("-created_at", "id"), page)

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

    def _page_queryset(self, queryset, page: PageRequest) -> Page[DomainInquiry]:
        total = queryset.count()
        objs = list(queryset[page.offset : page.offset + page.limit])
        return Page(items=[self._to_domain(o) for o in objs], total=total, limit=page.limit, offset=page.offset)

    @staticmethod
    def _date_range_boundary(value: date | datetime, *, end_of_day: bool) -> datetime:
        if isinstance(value, datetime):
            boundary = value
        else:
            boundary = datetime.combine(value, time.max if end_of_day else time.min)
        if timezone.is_naive(boundary):
            return timezone.make_aware(boundary)
        return boundary

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
