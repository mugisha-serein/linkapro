import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.config import require_env
from fastapi_app.dependencies import get_marketplace_search_cache
from fastapi_app.database import get_session
from fastapi_app.marketplace.models import VendorListingModel

router = APIRouter(prefix="/internal")
logger = logging.getLogger(__name__)
INTERNAL_SHARED_SECRET = require_env("FASTAPI_INTERNAL_SHARED_SECRET")


def _verify_internal_secret(x_internal_secret: str | None) -> None:
    if not x_internal_secret or x_internal_secret != INTERNAL_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized internal request.")


async def _upsert_listing_payload(payload: dict, session: AsyncSession) -> dict:
    vendor_id_value = payload.get("vendor_id")
    external_id_value = payload.get("external_id")
    approval_status = str(payload.get("approval_status") or payload.get("status") or "").strip().lower()
    is_approved = payload.get("is_approved") is True or approval_status == "approved"

    if not vendor_id_value and not external_id_value:
        raise HTTPException(
            status_code=400,
            detail="vendor_id or external_id is required for marketplace upsert.",
        )

    vendor_id = uuid.UUID(str(vendor_id_value)) if vendor_id_value else None
    external_id = str(external_id_value).strip() if external_id_value else None

    listing = None
    if external_id:
        result = await session.execute(
            select(VendorListingModel).where(VendorListingModel.external_id == external_id)
        )
        listing = result.scalar_one_or_none()
    if listing is None and vendor_id is not None:
        result = await session.execute(
            select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id)
        )
        listing = result.scalar_one_or_none()

    if not is_approved:
        if listing is not None:
            await session.delete(listing)
            await session.commit()
            await get_marketplace_search_cache().invalidate()
        return {"status": "ok", "listed": False}

    listing_data = {
        "business_name": payload.get("business_name") or "",
        "category": payload.get("category") or "other",
        "description": payload.get("description") or "",
        "service_area": payload.get("service_area") or "",
        "tags": _normalize_tags(payload.get("tags")),
        "cover_image_url": payload.get("cover_image_url"),
        "average_rating": payload.get("average_rating", 0.0),
        "total_reviews": payload.get("total_reviews", 0),
        "is_verified": payload.get("is_verified", False),
        "approval_status": "approved",
        "search_rank_score": payload.get("search_rank_score", 0.0),
    }

    if vendor_id is not None:
        listing_data["vendor_id"] = vendor_id
    if external_id is not None:
        listing_data["external_id"] = external_id

    if listing is None and vendor_id is None:
        raise HTTPException(
            status_code=400,
            detail="vendor_id is required when creating a new marketplace listing.",
        )

    if listing is None:
        listing = VendorListingModel(**listing_data)
        session.add(listing)
    else:
        for field, value in listing_data.items():
            setattr(listing, field, value)

    await session.commit()
    logger.info(
        "Marketplace listing upserted",
        extra={"vendor_id": str(vendor_id) if vendor_id else None, "external_id": external_id},
    )
    return {"status": "ok"}


@router.post("/listings")
async def upsert_listing(
    payload: dict,
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    """
    Ingest listing data from Django sync pipeline.
    """
    _verify_internal_secret(x_internal_secret)
    result = await _upsert_listing_payload(payload, session)
    await get_marketplace_search_cache().invalidate()
    return result


@router.post("/listings/", include_in_schema=False)
async def upsert_listing_with_trailing_slash(
    payload: dict,
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    _verify_internal_secret(x_internal_secret)
    result = await _upsert_listing_payload(payload, session)
    await get_marketplace_search_cache().invalidate()
    return result


@router.delete("/listings/{vendor_id}")
async def delete_listing(
    vendor_id: str,
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    _verify_internal_secret(x_internal_secret)
    result = await session.execute(
        select(VendorListingModel).where(VendorListingModel.vendor_id == uuid.UUID(vendor_id))
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        return {"status": "ok", "deleted": False}
    await session.delete(listing)
    await session.commit()
    await get_marketplace_search_cache().invalidate()
    return {"status": "ok", "deleted": True}


def _normalize_tags(tags_value) -> str:
    if not tags_value:
        return ""
    if isinstance(tags_value, str):
        return tags_value.strip()
    if isinstance(tags_value, (list, tuple, set)):
        cleaned = [str(tag).strip() for tag in tags_value if str(tag).strip()]
        return ", ".join(cleaned)
    return str(tags_value).strip()
