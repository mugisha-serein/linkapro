from __future__ import annotations

import uuid

from django.db.models import Count, Q
from django.utils import timezone

from application.vendors.analytics.dtos import VendorActivityDTO, VendorAnalyticsDTO, VendorDashboardSummaryDTO
from application.vendors.shared.dtos import PageDTO
from application.vendors.errors import VendorResourceNotFound
from domain.vendors.profile.entity import VendorProfile as DomainVendorProfile
from domain.vendors.profile.entity import profile_completion_errors_for
from domain.vendors.shared.pagination import PageRequest
from django_app.vendors.models import Inquiry, PortfolioImage, ServicePackage, VendorProfile as DjangoVendorProfile


class DjangoVendorAnalyticsReadRepositoryMixin:
    def dashboard_summary(self, vendor_id: uuid.UUID) -> VendorDashboardSummaryDTO:
        return VendorDashboardSummaryDTO(**self.vendor_metrics(vendor_id))

    def analytics(self, vendor_id: uuid.UUID) -> VendorAnalyticsDTO:
        metrics = self.vendor_metrics(vendor_id)
        total = metrics["total_inquiries"]
        read = metrics["read_inquiries"]
        analytics_metrics = {
            **metrics,
            "response_rate": round((read / total) * 100, 2) if total else 0.0,
        }
        return VendorAnalyticsDTO(
            **analytics_metrics,
            avg_response_time_hours=None,
            conversion_rate=None,
            unavailable_metrics=("avg_response_time_hours", "conversion_rate"),
        )

    def recent_activity(
        self,
        vendor_id: uuid.UUID,
        page: PageRequest | None = None,
    ) -> PageDTO[VendorActivityDTO]:
        self._require_vendor(vendor_id)
        page = page or PageRequest(limit=10, offset=0)
        inquiry_qs = (
            Inquiry.objects.filter(vendor_id=vendor_id)
            .order_by("-created_at", "id")
            .values("id", "created_at", "client_name", "is_read")
        )
        total = inquiry_qs.count()
        rows = list(inquiry_qs[page.offset : page.offset + page.limit])
        items = tuple(
            VendorActivityDTO(
                id=str(row["id"]),
                type="inquiry_read" if row["is_read"] else "inquiry_received",
                message=f"Inquiry from {row['client_name']}",
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        )
        return PageDTO(
            items=items,
            total=total,
            limit=page.limit,
            offset=page.offset,
            pagination_mode="cursor" if page.cursor else "offset",
        )

    def vendor_metrics(self, vendor_id: uuid.UUID) -> dict:
        profile = self._require_vendor(vendor_id)
        now = timezone.now()
        inquiry_counts = Inquiry.objects.filter(vendor_id=vendor_id).aggregate(
            total_inquiries=Count("id"),
            unread_inquiries=Count("id", filter=Q(is_read=False)),
            read_inquiries=Count("id", filter=Q(is_read=True)),
            inquiries_mtd=Count(
                "id",
                filter=Q(created_at__year=now.year, created_at__month=now.month),
            ),
        )
        package_counts = ServicePackage.all_objects.filter(
            vendor_id=vendor_id,
            is_deleted=False,
        ).aggregate(
            total_packages=Count("id"),
            active_packages=Count(
                "id",
                filter=Q(
                    is_active=True,
                    approval_status=ServicePackage.ApprovalStatus.APPROVED,
                ),
            ),
            approved_packages=Count(
                "id",
                filter=Q(approval_status=ServicePackage.ApprovalStatus.APPROVED),
            ),
            pending_packages=Count(
                "id",
                filter=Q(approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL),
            ),
            rejected_packages=Count(
                "id",
                filter=Q(approval_status=ServicePackage.ApprovalStatus.REJECTED),
            ),
        )
        portfolio_count = PortfolioImage.objects.filter(vendor_id=vendor_id).count()

        total_inquiries = inquiry_counts["total_inquiries"] or 0
        read_inquiries = inquiry_counts["read_inquiries"] or 0
        response_rate = round((read_inquiries / total_inquiries) * 100) if total_inquiries else 0

        return {
            "profile_completion": self.dashboard_completion_percentage(
                profile,
                portfolio_count,
                package_counts["total_packages"] or 0,
            ),
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
            "account_status": profile.status,
            "service_area": profile.service_area,
        }

    @staticmethod
    def _require_vendor(vendor_id: uuid.UUID) -> DjangoVendorProfile:
        try:
            return DjangoVendorProfile.objects.get(id=vendor_id)
        except DjangoVendorProfile.DoesNotExist as exc:
            raise VendorResourceNotFound("Vendor not found.", code="vendor_not_found") from exc

    @staticmethod
    def strict_profile_completion_errors(profile: object) -> dict[str, list[str]]:
        return profile_completion_errors_for(profile, DomainVendorProfile.required_profile_fields())

    @classmethod
    def dashboard_completion_percentage(cls, profile: object, portfolio_count: int, package_count: int) -> int:
        """Dashboard progress metric; strict submit eligibility is the domain completion error set."""
        required_fields = DomainVendorProfile.required_profile_fields()
        completion_errors = cls.strict_profile_completion_errors(profile)
        filled = sum(1 for field_name in required_fields if field_name not in completion_errors)
        if portfolio_count:
            filled += 1
        if package_count:
            filled += 1
        percentage = round((filled / (len(required_fields) + 2)) * 100)
        if completion_errors:
            return min(percentage, 99)
        return percentage
