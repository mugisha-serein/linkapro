from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from django_app.vendors.models import VendorProfile
from infrastructure.adapters.marketplace_projection import (
    delete_vendor_from_marketplace,
    sync_vendor_payload_to_marketplace,
)

from .models import MarketplaceProjectionOutbox

logger = logging.getLogger(__name__)
MAX_DELIVERY_ATTEMPTS = 5


def enqueue_vendor_projection(vendor: VendorProfile, *, reason: str | None = None) -> MarketplaceProjectionOutbox:
    event_type, payload = _projection_event_for_vendor(vendor, reason=reason)
    event = MarketplaceProjectionOutbox.objects.create(
        event_type=event_type,
        vendor_id=vendor.id,
        payload=payload,
    )
    transaction.on_commit(lambda: _schedule_outbox_delivery(event.id))
    logger.info(
        "marketplace_projection_outbox_enqueued",
        extra={"event_id": str(event.id), "vendor_id": str(vendor.id), "event_type": event.event_type},
    )
    return event


def enqueue_vendor_projection_by_id(vendor_id: UUID | str, *, reason: str | None = None) -> MarketplaceProjectionOutbox:
    vendor = VendorProfile.objects.get(id=vendor_id)
    return enqueue_vendor_projection(vendor, reason=reason)


def deliver_marketplace_projection_outbox_event(event_id: UUID | str) -> bool:
    event = MarketplaceProjectionOutbox.objects.get(id=event_id)
    if event.status == MarketplaceProjectionOutbox.Status.DELIVERED:
        return True
    if event.status == MarketplaceProjectionOutbox.Status.FAILED:
        return False

    event.status = MarketplaceProjectionOutbox.Status.PROCESSING
    event.attempts += 1
    event.last_error = None
    event.save(update_fields=["status", "attempts", "last_error", "updated_at"])

    try:
        result = _deliver_event(event)
    except Exception as exc:
        _mark_delivery_failed_or_pending(event, exc)
        raise

    event.status = MarketplaceProjectionOutbox.Status.DELIVERED
    event.delivered_at = timezone.now()
    event.last_error = None
    event.payload = {**event.payload, "delivery_result": result}
    event.save(update_fields=["status", "delivered_at", "last_error", "payload", "updated_at"])
    logger.info(
        "marketplace_projection_outbox_delivered",
        extra={"event_id": str(event.id), "vendor_id": str(event.vendor_id), "attempts": event.attempts},
    )
    return True


def _deliver_event(event: MarketplaceProjectionOutbox) -> dict:
    payload = event.payload
    if event.event_type == MarketplaceProjectionOutbox.EventType.DELETE_VENDOR:
        return delete_vendor_from_marketplace(event.vendor_id)
    if event.event_type == MarketplaceProjectionOutbox.EventType.UPSERT_VENDOR:
        return sync_vendor_payload_to_marketplace(
            vendor_id=payload["vendor_id"],
            business_name=payload["business_name"],
            category=payload["category"],
            description=payload["description"],
            service_area=payload["service_area"],
            cover_image_url=payload.get("cover_image_url"),
            approval_status=payload.get("approval_status", VendorProfile.Status.APPROVED),
        )
    raise ValueError(f"Unsupported marketplace projection event type: {event.event_type}")


def _mark_delivery_failed_or_pending(event: MarketplaceProjectionOutbox, exc: Exception) -> None:
    error = f"{exc.__class__.__name__}: {exc}"
    if event.attempts >= MAX_DELIVERY_ATTEMPTS:
        event.status = MarketplaceProjectionOutbox.Status.FAILED
    else:
        event.status = MarketplaceProjectionOutbox.Status.PENDING
        event.next_attempt_at = timezone.now() + timedelta(minutes=min(30, 2 ** event.attempts))
    event.last_error = error[:4000]
    event.save(update_fields=["status", "next_attempt_at", "last_error", "updated_at"])
    logger.warning(
        "marketplace_projection_outbox_delivery_failed",
        extra={"event_id": str(event.id), "vendor_id": str(event.vendor_id), "attempts": event.attempts},
        exc_info=True,
    )


def _projection_event_for_vendor(vendor: VendorProfile, *, reason: str | None = None) -> tuple[str, dict]:
    if _is_vendor_listable(vendor):
        return MarketplaceProjectionOutbox.EventType.UPSERT_VENDOR, _vendor_payload(vendor, reason=reason)
    return MarketplaceProjectionOutbox.EventType.DELETE_VENDOR, {
        "vendor_id": str(vendor.id),
        "approval_status": vendor.status,
        "reason": reason or "vendor_not_listable",
    }


def _is_vendor_listable(vendor: VendorProfile) -> bool:
    return vendor.status == VendorProfile.Status.APPROVED and vendor.is_profile_complete


def _vendor_payload(vendor: VendorProfile, *, reason: str | None = None) -> dict:
    return {
        "vendor_id": str(vendor.id),
        "business_name": vendor.business_name,
        "category": vendor.category,
        "custom_category": vendor.custom_category if vendor.category == VendorProfile.Category.OTHER else None,
        "description": vendor.description,
        "service_area": vendor.service_area,
        "cover_image_url": None,
        "approval_status": VendorProfile.Status.APPROVED,
        "is_approved": True,
        "is_verified": True,
        "reason": reason or "vendor_listable",
        "source_updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None,
    }


def _schedule_outbox_delivery(event_id: UUID) -> None:
    try:
        from tasks.marketplace_sync import deliver_marketplace_projection_outbox_event_task

        deliver_marketplace_projection_outbox_event_task.delay(str(event_id))
    except Exception:
        logger.warning("marketplace_projection_outbox_task_schedule_failed", extra={"event_id": str(event_id)}, exc_info=True)
