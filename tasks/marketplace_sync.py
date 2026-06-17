from infrastructure.adapters.marketplace_projection import (
    delete_vendor_from_marketplace,
    sync_vendor_payload_to_marketplace,
)


def sync_vendor_listing_to_fastapi(
    vendor_id: str,
    business_name: str,
    category: str,
    description: str,
    service_area: str,
    cover_image_url: str = None,
    approval_status: str = "approved",
):
    return sync_vendor_payload_to_marketplace(
        vendor_id=vendor_id,
        business_name=business_name,
        category=category,
        description=description,
        service_area=service_area,
        cover_image_url=cover_image_url,
        approval_status=approval_status,
    )


def delete_vendor_listing_from_fastapi(vendor_id: str):
    return delete_vendor_from_marketplace(vendor_id)
