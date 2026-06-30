import logging

from celery import shared_task

from django_app.governance.marketplace_outbox import deliver_marketplace_projection_outbox_event
from infrastructure.adapters.marketplace_projection import (
    delete_vendor_from_marketplace,
    sync_vendor_payload_to_marketplace,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    retry_backoff=True,
    retry_jitter=True,
    name="tasks.marketplace_sync.deliver_marketplace_projection_outbox_event_task",
)
def deliver_marketplace_projection_outbox_event_task(self, event_id: str) -> bool:
    try:
        return deliver_marketplace_projection_outbox_event(event_id)
    except Exception as exc:
        logger.warning(
            "marketplace_projection_outbox_retry_scheduled",
            extra={"event_id": event_id, "attempt": int(getattr(self.request, "retries", 0) or 0) + 1},
            exc_info=True,
        )
        raise self.retry(exc=exc)


def sync_vendor_listing_to_fastapi(
    vendor_id: str,
    business_name: str,
    category: str,
    description: str,
    service_area: str,
    cover_image_url: str = None,
    approval_status: str = "approved",
    starting_price: str | None = None,
    min_package_price: str | None = None,
    max_package_price: str | None = None,
    currency: str | None = None,
):
    return sync_vendor_payload_to_marketplace(
        vendor_id=vendor_id,
        business_name=business_name,
        category=category,
        description=description,
        service_area=service_area,
        cover_image_url=cover_image_url,
        approval_status=approval_status,
        starting_price=starting_price,
        min_package_price=min_package_price,
        max_package_price=max_package_price,
        currency=currency,
    )


def delete_vendor_listing_from_fastapi(vendor_id: str):
    return delete_vendor_from_marketplace(vendor_id)
