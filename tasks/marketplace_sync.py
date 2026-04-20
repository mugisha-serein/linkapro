from celery import shared_task
import httpx
from django.conf import settings

@shared_task
def sync_vendor_listing_to_fastapi(vendor_id: str, business_name: str, category: str, description: str, service_area: str, cover_image_url: str = None):
    # In production, use internal service call or shared DB access
    # For simplicity, call FastAPI internal endpoint (could use repository directly if shared)
    payload = {
        "vendor_id": vendor_id,
        "business_name": business_name,
        "category": category,
        "description": description,
        "service_area": service_area,
        "cover_image_url": cover_image_url,
    }
    try:
        response = httpx.post(f"{settings.FASTAPI_INTERNAL_URL}/internal/listings/", json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        # Log error
        pass