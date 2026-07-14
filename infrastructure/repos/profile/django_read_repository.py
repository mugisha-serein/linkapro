from __future__ import annotations

import uuid

from application.vendors.dtos import (
    PageDTO,
    ServicePackageDTO,
)
from application.vendors.ports import VendorReadPort
from domain.vendors.shared.pagination import PageRequest
from django_app.vendors.models import ServicePackage
from infrastructure.repos.analytics.django_read_repository import DjangoVendorAnalyticsReadRepositoryMixin


class DjangoVendorReadRepository(DjangoVendorAnalyticsReadRepositoryMixin, VendorReadPort):
    def list_service_packages(
        self,
        vendor_id: uuid.UUID,
        page: PageRequest | None = None,
    ) -> PageDTO[ServicePackageDTO]:
        self._require_vendor(vendor_id)
        page = page or PageRequest()
        queryset = (
            ServicePackage.all_objects.filter(vendor_id=vendor_id, is_deleted=False)
            .order_by("-created_at", "id")
            .values(
                "id",
                "vendor_id",
                "name",
                "description",
                "price",
                "currency",
                "package_tier",
                "approval_status",
                "rejection_reason",
                "is_active",
                "is_deleted",
                "deleted_at",
                "last_approved_at",
                "last_vendor_public_edit_at",
                "next_vendor_edit_allowed_at",
                "version",
            )
        )
        total = queryset.count()
        rows = list(queryset[page.offset : page.offset + page.limit])
        return PageDTO(
            items=tuple(ServicePackageDTO(**row) for row in rows),
            total=total,
            limit=page.limit,
            offset=page.offset,
            pagination_mode="cursor" if page.cursor else "offset",
        )
