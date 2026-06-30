import logging
import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.config import require_env
from fastapi_app.dependencies import get_marketplace_search_cache
from fastapi_app.database import get_session
from fastapi_app.marketplace.models import VendorListingModel
from fastapi_app.schemas import InternalListingUpsertRequest
from infrastructure.security.service_auth import ServiceAuthError, assert_service_request

router = APIRouter(prefix="/internal")
logger = logging.getLogger(__name__)
INTERNAL_SHARED_SECRET = require_env("FASTAPI_INTERNAL_SHARED_SECRET")


async def _verified_body(
    request: Request,
    service_name: str | None,
    request_timestamp: str | None,
    request_id: str | None,
    payload_sha256: str | None,
    service_mac: str | None,
    legacy_secret: str | None = None,
) -> bytes:
    body = await request.body()
    if _allow_legacy_internal_secret(legacy_secret):
        return body
    try:
        assert_service_request(
            key=INTERNAL_SHARED_SECRET,
            service=service_name,
            method=request.method,
            path=request.url.path,
            timestamp=request_timestamp,
            request_id=request_id,
            payload_hash=payload_sha256,
            supplied_mac=service_mac,
            payload=body,
        )
    except ServiceAuthError:
        logger.warning("internal_service_auth_failed", extra={"path": request.url.path, "request_id": request_id})
        raise HTTPException(status_code=401, detail="Unauthorized internal request.")
    return body


def _allow_legacy_internal_secret(legacy_secret: str | None) -> bool:
    if not legacy_secret or legacy_secret != INTERNAL_SHARED_SECRET:
        return False
    return os.getenv("FASTAPI_ENV", "development").strip().lower() != "production"


def _parse_listing_payload(body: bytes) -> InternalListingUpsertRequest:
    try:
        return InternalListingUpsertRequest.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


async def _upsert_listing_payload(payload: InternalListingUpsertRequest, session: AsyncSession) -> dict:
    vendor_id = payload.vendor_id
    external_id = payload.external_id.strip() if payload.external_id else None
    approval_status = str(payload.approval_status or payload.status or "").strip().lower()
    is_approved = payload.is_approved is True or approval_status == "approved"

    result = await session.execute(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_id))
    listing = result.scalar_one_or_none()
    if listing is None and external_id:
        result = await session.execute(select(VendorListingModel).where(VendorListingModel.external_id == external_id))
        listing = result.scalar_one_or_none()

    if not is_approved:
        if listing is not None:
            await session.delete(listing)
            await session.commit()
        return {"status": "ok", "listed": False}

    listing_data = {
        "vendor_id": vendor_id,
        "business_name": payload.business_name,
        "category": payload.category,
        "description": payload.description,
        "service_area": payload.service_area,
        "tags": _normalize_tags(payload.tags),
        "cover_image_url": payload.cover_image_url,
        "average_rating": payload.average_rating,
        "total_reviews": payload.total_reviews,
        "is_verified": payload.is_verified,
        "approval_status": "approved",
        "search_rank_score": payload.search_rank_score,
        "starting_price": payload.starting_price,
        "min_package_price": payload.min_package_price,
        "max_package_price": payload.max_package_price,
        "currency": payload.currency,
    }
    if external_id is not None:
        listing_data["external_id"] = external_id

    if listing is None:
        listing = VendorListingModel(**listing_data)
        session.add(listing)
    else:
        for field, value in listing_data.items():
            setattr(listing, field, value)

    await session.commit()
    logger.info("Marketplace listing upserted", extra={"vendor_id": str(vendor_id), "external_id": external_id})
    return {"status": "ok"}


@router.post("/listings")
async def upsert_listing(
    request: Request,
    x_service_name: str | None = Header(default=None, alias="X-Service-Name"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_payload_sha256: str | None = Header(default=None, alias="X-Payload-SHA256"),
    x_service_mac: str | None = Header(default=None, alias="X-Service-MAC"),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    body = await _verified_body(request, x_service_name, x_request_timestamp, x_request_id, x_payload_sha256, x_service_mac, x_internal_secret)
    result = await _upsert_listing_payload(_parse_listing_payload(body), session)
    await _invalidate_marketplace_cache()
    return result


@router.post("/listings/", include_in_schema=False)
async def upsert_listing_with_trailing_slash(
    request: Request,
    x_service_name: str | None = Header(default=None, alias="X-Service-Name"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_payload_sha256: str | None = Header(default=None, alias="X-Payload-SHA256"),
    x_service_mac: str | None = Header(default=None, alias="X-Service-MAC"),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    body = await _verified_body(request, x_service_name, x_request_timestamp, x_request_id, x_payload_sha256, x_service_mac, x_internal_secret)
    result = await _upsert_listing_payload(_parse_listing_payload(body), session)
    await _invalidate_marketplace_cache()
    return result


@router.delete("/listings/{vendor_id}")
async def delete_listing(
    request: Request,
    vendor_id: str,
    x_service_name: str | None = Header(default=None, alias="X-Service-Name"),
    x_request_timestamp: str | None = Header(default=None, alias="X-Request-Timestamp"),
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_payload_sha256: str | None = Header(default=None, alias="X-Payload-SHA256"),
    x_service_mac: str | None = Header(default=None, alias="X-Service-MAC"),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
    session: AsyncSession = Depends(get_session),
):
    await _verified_body(request, x_service_name, x_request_timestamp, x_request_id, x_payload_sha256, x_service_mac, x_internal_secret)
    try:
        vendor_uuid = uuid.UUID(vendor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vendor_id.")
    result = await session.execute(select(VendorListingModel).where(VendorListingModel.vendor_id == vendor_uuid))
    listing = result.scalar_one_or_none()
    if listing is None:
        return {"status": "ok", "deleted": False}
    await session.delete(listing)
    await session.commit()
    await _invalidate_marketplace_cache()
    return {"status": "ok", "deleted": True}


async def _invalidate_marketplace_cache() -> None:
    cache = get_marketplace_search_cache()
    if cache is None:
        return
    await cache.invalidate()


def _normalize_tags(tags_value) -> str:
    if not tags_value:
        return ""
    if isinstance(tags_value, str):
        return tags_value.strip()
    if isinstance(tags_value, (list, tuple, set)):
        cleaned = [str(tag).strip() for tag in tags_value if str(tag).strip()]
        return ", ".join(cleaned)
    return str(tags_value).strip()
