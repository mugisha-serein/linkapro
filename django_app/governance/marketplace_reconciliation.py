from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django_app.vendors.models import VendorProfile
from infrastructure.adapters.marketplace_projection import (
    delete_vendor_from_marketplace,
    list_marketplace_projection_vendor_ids,
)

from .marketplace_outbox import enqueue_vendor_projection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketplaceReconciliationResult:
    django_approved_complete_count: int
    fastapi_projection_count: int
    stale_projection_count: int
    deleted_stale_count: int
    upsert_enqueued_count: int
    dry_run: bool = False
    stale_vendor_ids: list[str] = field(default_factory=list)
    approved_vendor_ids: list[str] = field(default_factory=list)


def reconcile_marketplace_projection(*, dry_run: bool = False) -> MarketplaceReconciliationResult:
    approved_vendors = _approved_complete_vendors()
    approved_vendor_ids = {str(vendor.id) for vendor in approved_vendors}
    fastapi_vendor_ids = set(list_marketplace_projection_vendor_ids())
    stale_vendor_ids = sorted(fastapi_vendor_ids - approved_vendor_ids)

    upsert_enqueued_count = 0
    deleted_stale_count = 0
    if not dry_run:
        for vendor in approved_vendors:
            enqueue_vendor_projection(vendor, reason="marketplace_reconciliation")
            upsert_enqueued_count += 1
        for vendor_id in stale_vendor_ids:
            delete_vendor_from_marketplace(vendor_id)
            deleted_stale_count += 1

    result = MarketplaceReconciliationResult(
        django_approved_complete_count=len(approved_vendors),
        fastapi_projection_count=len(fastapi_vendor_ids),
        stale_projection_count=len(stale_vendor_ids),
        deleted_stale_count=deleted_stale_count,
        upsert_enqueued_count=upsert_enqueued_count,
        dry_run=dry_run,
        stale_vendor_ids=stale_vendor_ids,
        approved_vendor_ids=sorted(approved_vendor_ids),
    )
    logger.info(
        "marketplace_projection_reconciliation_completed",
        extra={
            "django_approved_complete_count": result.django_approved_complete_count,
            "fastapi_projection_count": result.fastapi_projection_count,
            "stale_projection_count": result.stale_projection_count,
            "deleted_stale_count": result.deleted_stale_count,
            "upsert_enqueued_count": result.upsert_enqueued_count,
            "dry_run": result.dry_run,
        },
    )
    return result


def _approved_complete_vendors() -> list[VendorProfile]:
    candidates = VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED).select_related("user").order_by("id")
    return [vendor for vendor in candidates if vendor.is_profile_complete]
