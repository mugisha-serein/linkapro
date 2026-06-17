import logging
from typing import Any
from uuid import UUID

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from django_app.vendors.models import VendorProfile

logger = logging.getLogger(__name__)


def sync_vendor_to_marketplace(vendor: VendorProfile) -> dict:
    if not _is_vendor_listable(vendor):
        logger.info(
            "Vendor is not eligible for marketplace listing; deleting projection.",
            extra={"vendor_id": str(vendor.id), "status": vendor.status},
        )
        result = delete_vendor_from_marketplace(vendor.id)
        result.setdefault("reason", "vendor_not_listable")
        return result

    config = _get_marketplace_config()
    if config is None:
        return {"status": "skipped", "reason": "marketplace_projection_not_configured"}

    payload = _vendor_payload(vendor)
    response = httpx.post(
        f"{config['base_url']}/internal/listings",
        json=payload,
        timeout=10,
        headers={"X-Internal-Secret": config["shared_secret"]},
    )
    response.raise_for_status()
    logger.info("Marketplace projection synced.", extra={"vendor_id": str(vendor.id)})
    return response.json()


def delete_vendor_from_marketplace(vendor_id: UUID | str) -> dict:
    config = _get_marketplace_config()
    if config is None:
        return {"status": "skipped", "reason": "marketplace_projection_not_configured"}

    response = httpx.delete(
        f"{config['base_url']}/internal/listings/{vendor_id}",
        timeout=10,
        headers={"X-Internal-Secret": config["shared_secret"]},
    )
    response.raise_for_status()
    logger.info("Marketplace projection deleted.", extra={"vendor_id": str(vendor_id)})
    return response.json()


def sync_or_delete_vendor_projection(vendor: VendorProfile) -> dict:
    if _is_vendor_listable(vendor):
        return sync_vendor_to_marketplace(vendor)
    return delete_vendor_from_marketplace(vendor.id)


def sync_vendor_payload_to_marketplace(
    *,
    vendor_id: UUID | str,
    business_name: str,
    category: str,
    description: str,
    service_area: str,
    cover_image_url: str | None = None,
    approval_status: str = "approved",
) -> dict:
    config = _get_marketplace_config()
    if config is None:
        return {"status": "skipped", "reason": "marketplace_projection_not_configured"}

    payload = {
        "vendor_id": str(vendor_id),
        "business_name": business_name,
        "category": category,
        "description": description,
        "service_area": service_area,
        "cover_image_url": cover_image_url,
        "approval_status": approval_status,
        "is_approved": approval_status == VendorProfile.Status.APPROVED,
    }
    response = httpx.post(
        f"{config['base_url']}/internal/listings",
        json=payload,
        timeout=10,
        headers={"X-Internal-Secret": config["shared_secret"]},
    )
    response.raise_for_status()
    logger.info("Marketplace projection payload synced.", extra={"vendor_id": str(vendor_id)})
    return response.json()


def _get_marketplace_config() -> dict[str, str] | None:
    base_url = (getattr(settings, "FASTAPI_INTERNAL_URL", None) or "").strip().rstrip("/")
    shared_secret = (getattr(settings, "FASTAPI_INTERNAL_SHARED_SECRET", None) or "").strip()

    if base_url and shared_secret:
        return {"base_url": base_url, "shared_secret": shared_secret}

    message = "FASTAPI_INTERNAL_URL and FASTAPI_INTERNAL_SHARED_SECRET must be configured for marketplace projection sync."
    if _allow_unconfigured_projection():
        logger.warning("[Marketplace Projection Skipped] %s", message)
        return None
    raise ImproperlyConfigured(message)


def _allow_unconfigured_projection() -> bool:
    settings_module = getattr(settings, "SETTINGS_MODULE", "")
    return bool(getattr(settings, "DEBUG", False)) or settings_module.endswith((".development", ".test"))


def _is_vendor_listable(vendor: VendorProfile) -> bool:
    return vendor.status == VendorProfile.Status.APPROVED and vendor.is_profile_complete


def _vendor_payload(vendor: VendorProfile) -> dict[str, Any]:
    return {
        "vendor_id": str(vendor.id),
        "business_name": vendor.business_name,
        "category": vendor.category,
        "description": vendor.description,
        "service_area": vendor.service_area,
        "cover_image_url": None,
        "approval_status": VendorProfile.Status.APPROVED,
        "is_approved": True,
    }
