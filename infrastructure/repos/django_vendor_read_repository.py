from __future__ import annotations

import uuid

from django.db.models import Count, Q
from django.utils import timezone

from application.vendors.dtos import ServicePackageDTO
from domain.vendors.interfaces import Page, PageRequest
from django_app.vendors.models import (
    Inquiry,
    PortfolioImage,
    ServicePackage,
    VendorProfile,
)


class DjangoVendorReadRepository:
    def list_service_packages(self, vendor_id: uuid.UUID, page: PageRequest | None = None) -> Page[ServicePackageDTO]:
        page = page or PageRequest()
        queryset = (
            ServicePackage.objects.filter(vendor_id=vendor_id)
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
            )
        )
        total = queryset.count()
        rows = list(queryset[page.offset : page.offset + page.limit])
        return Page(
            items=[ServicePackageDTO(**row) for row in rows],
            total=total,
            limit=page.limit,
            offset=page.offset,
        )

    def vendor_metrics(self, vendor_id: uuid.UUID) -> dict:
        profile = (
            VendorProfile.objects.filter(id=vendor_id)
            .values("business_name", "description", "service_area", "contact_email", "contact_phone", "status")
            .first()
        )
        now = timezone.now()
        inquiry_counts = Inquiry.objects.filter(vendor_id=vendor_id).aggregate(
            total_inquiries=Count("id"),
            unread_inquiries=Count("id", filter=Q(is_read=False)),
            read_inquiries=Count("id", filter=Q(is_read=True)),
            inquiries_mtd=Count("id", filter=Q(created_at__year=now.year, created_at__month=now.month)),
        )
        package_counts = ServicePackage.all_objects.filter(vendor_id=vendor_id, is_deleted=False).aggregate(
            total_packages=Count("id"),
            active_packages=Count("id", filter=Q(is_active=True, approval_status=ServicePackage.ApprovalStatus.APPROVED)),
            approved_packages=Count("id", filter=Q(approval_status=ServicePackage.ApprovalStatus.APPROVED)),
            pending_packages=Count("id", filter=Q(approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL)),
            rejected_packages=Count("id", filter=Q(approval_status=ServicePackage.ApprovalStatus.REJECTED)),
        )
        portfolio_count = PortfolioImage.objects.filter(vendor_id=vendor_id).count()

        total_inquiries = inquiry_counts["total_inquiries"] or 0
        read_inquiries = inquiry_counts["read_inquiries"] or 0
        response_rate = round((read_inquiries / total_inquiries) * 100) if total_inquiries else 0

        return {
            "profile_completion": self._profile_completion_score(profile, portfolio_count, package_counts["total_packages"] or 0),
            "total_inquiries": total_inquiries,
            "inquiries_mtd": inquiry_counts["inquiries_mtd"] or 0,
            "unread_inquiries": inquiry_counts["unread_inquiries"] or 0,
            "read_inquiries": read_inquiries,
            "response_rate": response_rate,
            "total_packages": package_counts["total_packages"] or 0,
            "active_packages": package_counts["active_packages"] or 0,
            "approved_packages": package_counts["approved_packages"] or 0,
            "pending_packages": package_counts["pending_packages"] or 0,
            "rejected_packages": package_counts["rejected_packages"] or 0,
            "portfolio_count": portfolio_count,
            "account_status": profile["status"] if profile else "draft",
            "service_area": profile["service_area"] if profile else "",
        }

    @staticmethod
    def _profile_completion_score(profile: dict | None, portfolio_count: int, package_count: int) -> int:
        if not profile:
            return 0
        fields = [
            profile["business_name"],
            profile["description"],
            profile["service_area"],
            profile["contact_email"],
            profile["contact_phone"],
        ]
        filled = sum(1 for value in fields if value)
        if portfolio_count:
            filled += 1
        if package_count:
            filled += 1
        total = len(fields) + 2
        return round((filled / total) * 100)
