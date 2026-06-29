from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from .models import PortfolioImage, ServicePackage, VendorProfile
from .serializers import public_portfolio_display_url


@dataclass(frozen=True)
class VendorApprovalResult:
    vendor: VendorProfile
    packages_approved: int
    portfolio_items_approved: int
    portfolio_items_skipped: int

    def summary(self) -> dict:
        return {
            "packages_approved": self.packages_approved,
            "portfolio_items_approved": self.portfolio_items_approved,
            "portfolio_items_skipped": self.portfolio_items_skipped,
        }


def approve_pending_vendor_submission(vendor_id: UUID) -> VendorApprovalResult:
    """Approve a pending vendor and all eligible submitted vendor content together."""

    with transaction.atomic():
        vendor = VendorProfile.objects.select_for_update().get(id=vendor_id)
        if vendor.status != VendorProfile.Status.PENDING_REVIEW:
            raise ValueError("Vendor must be submitted for review before approval.")

        now = timezone.now()
        vendor.status = VendorProfile.Status.APPROVED
        vendor.approved_at = now
        vendor.rejected_at = None
        vendor.rejection_reason = None
        vendor.save(update_fields=["status", "approved_at", "rejected_at", "rejection_reason", "updated_at"])

        package_ids = list(
            ServicePackage.objects.select_for_update()
            .filter(
                vendor_id=vendor.id,
                approval_status=ServicePackage.ApprovalStatus.WAITING_APPROVAL,
                is_deleted=False,
            )
            .values_list("id", flat=True)
        )
        packages_approved = 0
        if package_ids:
            packages_approved = ServicePackage.objects.filter(id__in=package_ids).update(
                approval_status=ServicePackage.ApprovalStatus.APPROVED,
                rejection_reason=None,
                is_active=True,
                updated_at=now,
            )

        portfolio_candidates = list(
            PortfolioImage.objects.select_for_update().filter(
                vendor_id=vendor.id,
                is_deleted=False,
                upload_status=PortfolioImage.UploadStatus.UPLOADED,
                quality_status=PortfolioImage.QualityStatus.PASSED,
                visibility_status__in=[
                    PortfolioImage.VisibilityStatus.PRIVATE,
                    PortfolioImage.VisibilityStatus.WAITING_APPROVAL,
                ],
            )
        )
        eligible_portfolio_ids = [
            item.id
            for item in portfolio_candidates
            if public_portfolio_display_url(item)
        ]
        portfolio_items_approved = 0
        if eligible_portfolio_ids:
            portfolio_items_approved = PortfolioImage.objects.filter(id__in=eligible_portfolio_ids).update(
                visibility_status=PortfolioImage.VisibilityStatus.APPROVED,
                rejection_reason=None,
                is_active=True,
                updated_at=now,
            )

        return VendorApprovalResult(
            vendor=vendor,
            packages_approved=packages_approved,
            portfolio_items_approved=portfolio_items_approved,
            portfolio_items_skipped=len(portfolio_candidates) - len(eligible_portfolio_ids),
        )
