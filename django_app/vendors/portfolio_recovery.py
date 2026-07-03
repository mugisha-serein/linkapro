from __future__ import annotations

import logging
from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction

from django_app.vendors.models import PortfolioImage
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from tasks.image_tasks import process_vendor_portfolio_media_task

logger = logging.getLogger(__name__)

ALREADY_COMPLETE = "already_complete"
HAS_CLOUDINARY_URL_NEEDS_PROCESSING = "has_cloudinary_url_needs_processing"
HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL = "has_cloudinary_public_id_missing_url"
HAS_TEMP_FILE_CAN_UPLOAD = "has_temp_file_can_upload"
MISSING_SOURCE_UNRECOVERABLE = "missing_source_unrecoverable"

RECOVERY_CATEGORIES = (
    ALREADY_COMPLETE,
    HAS_CLOUDINARY_URL_NEEDS_PROCESSING,
    HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL,
    HAS_TEMP_FILE_CAN_UPLOAD,
    MISSING_SOURCE_UNRECOVERABLE,
)

UNRECOVERABLE_MESSAGE = (
    "Portfolio media source is no longer available. Upload the file again to continue review."
)


def recover_stuck_portfolio_media(*, dry_run: bool = True, limit: int | None = None) -> dict[str, Any]:
    queryset = PortfolioImage.objects.filter(is_active=True).select_related("vendor").order_by("created_at")
    if limit is not None:
        queryset = queryset[:limit]

    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "limit": limit,
        "scanned": 0,
        "updated": 0,
        "queued": 0,
        "unrecoverable": 0,
        "categories": {category: 0 for category in RECOVERY_CATEGORIES},
        "items": [],
    }

    for image in queryset:
        summary["scanned"] += 1
        item = _recover_portfolio_image(image, dry_run=dry_run)
        summary["categories"][item["category"]] += 1
        if item.get("updated"):
            summary["updated"] += 1
        if item.get("queued"):
            summary["queued"] += 1
        if item["category"] == MISSING_SOURCE_UNRECOVERABLE:
            summary["unrecoverable"] += 1
        summary["items"].append(item)

    return summary


def _recover_portfolio_image(image: PortfolioImage, *, dry_run: bool) -> dict[str, Any]:
    url = _media_url(image)
    public_id = _cloudinary_public_id(image)

    if _is_complete(image, url):
        return _item(image, ALREADY_COMPLETE, "Portfolio media is already complete.")

    if url:
        return _queue_existing_remote_media(image, url, dry_run=dry_run)

    if public_id:
        restored = _restore_from_cloudinary_public_id(image, public_id, dry_run=dry_run)
        if restored:
            return restored

    if _temp_file_exists(image.temp_upload_path):
        return _upload_existing_temp_file(image, dry_run=dry_run)

    return _mark_unrecoverable(image, dry_run=dry_run)


def _queue_existing_remote_media(image: PortfolioImage, url: str, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return _item(image, HAS_CLOUDINARY_URL_NEEDS_PROCESSING, "Existing Cloudinary URL can be requeued.")

    updates = {
        "secure_url": image.secure_url or url,
        "cloudinary_secure_url": image.cloudinary_secure_url or url,
    }
    _prepare_for_processing(image, updates)
    _dispatch_processing(image)
    return _item(
        image,
        HAS_CLOUDINARY_URL_NEEDS_PROCESSING,
        "Existing Cloudinary URL was requeued for processing.",
        updated=True,
        queued=True,
    )


def _restore_from_cloudinary_public_id(
    image: PortfolioImage,
    public_id: str,
    *,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run:
        return _item(
            image,
            HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL,
            "Cloudinary public ID can be checked for a missing secure URL.",
        )

    try:
        resource = CloudinaryAdapter().get_resource(public_id, resource_type=_resource_type(image))
    except Exception:
        logger.exception(
            "Portfolio media Cloudinary lookup failed.",
            extra={"image_id": str(image.id), "public_id": public_id},
        )
        if _temp_file_exists(image.temp_upload_path):
            return None
        return _item(
            image,
            HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL,
            "Cloudinary public ID lookup failed; portfolio row was left unchanged.",
        )

    secure_url = (resource or {}).get("secure_url")
    if not secure_url:
        return None

    updates = {
        "public_id": image.public_id or public_id,
        "secure_url": secure_url,
        "cloudinary_public_id": image.cloudinary_public_id or public_id,
        "cloudinary_secure_url": secure_url,
        "width": resource.get("width") or image.width,
        "height": resource.get("height") or image.height,
        "duration_seconds": resource.get("duration") or image.duration_seconds,
    }
    _prepare_for_processing(image, updates)
    _dispatch_processing(image)
    return _item(
        image,
        HAS_CLOUDINARY_PUBLIC_ID_MISSING_URL,
        "Missing Cloudinary secure URL was restored and requeued.",
        updated=True,
        queued=True,
    )


def _upload_existing_temp_file(image: PortfolioImage, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return _item(image, HAS_TEMP_FILE_CAN_UPLOAD, "Existing temp file can be uploaded to shared storage.")

    temp_upload_path = image.temp_upload_path
    try:
        with default_storage.open(temp_upload_path, "rb") as upload_file:
            if image.media_type == PortfolioImage.MediaType.VIDEO:
                result = CloudinaryAdapter().upload_file(
                    upload_file,
                    folder="vendor_portfolio",
                    public_id=str(image.id),
                    resource_type="video",
                )
            else:
                result = CloudinaryAdapter().upload_image(upload_file, fallback_to_storage=False)
    except Exception:
        logger.exception(
            "Portfolio media temp-file recovery upload failed.",
            extra={"image_id": str(image.id), "temp_upload_path": temp_upload_path},
        )
        return _item(
            image,
            HAS_TEMP_FILE_CAN_UPLOAD,
            "Temp file upload to shared storage failed; portfolio row was left unchanged.",
        )

    updates = {
        "public_id": result["public_id"],
        "secure_url": result["secure_url"],
        "cloudinary_public_id": result["public_id"],
        "cloudinary_secure_url": result["secure_url"],
        "temp_upload_path": None,
        "local_preview_url": None,
    }
    _prepare_for_processing(image, updates)
    _delete_temp_file(temp_upload_path, image_id=str(image.id))
    _dispatch_processing(image)
    return _item(
        image,
        HAS_TEMP_FILE_CAN_UPLOAD,
        "Existing temp file was uploaded to shared storage and requeued.",
        updated=True,
        queued=True,
    )


def _mark_unrecoverable(image: PortfolioImage, *, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return _item(
            image,
            MISSING_SOURCE_UNRECOVERABLE,
            "No Cloudinary URL, public ID, or temp file is available.",
        )

    with transaction.atomic():
        image.upload_status = PortfolioImage.UploadStatus.FAILED
        image.visibility_status = PortfolioImage.VisibilityStatus.PRIVATE
        image.upload_error = UNRECOVERABLE_MESSAGE
        image.failure_reason = UNRECOVERABLE_MESSAGE
        image.local_preview_url = None
        image.save(
            update_fields=[
                "upload_status",
                "visibility_status",
                "upload_error",
                "failure_reason",
                "local_preview_url",
                "updated_at",
            ]
        )
    logger.warning("Portfolio media marked unrecoverable.", extra={"image_id": str(image.id)})
    return _item(
        image,
        MISSING_SOURCE_UNRECOVERABLE,
        UNRECOVERABLE_MESSAGE,
        updated=True,
    )


def _prepare_for_processing(image: PortfolioImage, updates: dict[str, Any]) -> None:
    with transaction.atomic():
        for field, value in updates.items():
            setattr(image, field, value)
        image.upload_status = PortfolioImage.UploadStatus.QUEUED
        image.quality_status = PortfolioImage.QualityStatus.PENDING_ANALYSIS
        image.visibility_status = PortfolioImage.VisibilityStatus.PRIVATE
        image.upload_error = None
        image.failure_reason = None
        image.save(
            update_fields=[
                *updates.keys(),
                "upload_status",
                "quality_status",
                "visibility_status",
                "upload_error",
                "failure_reason",
                "updated_at",
            ]
        )
    logger.info("Portfolio media requeued for processing.", extra={"image_id": str(image.id)})


def _dispatch_processing(image: PortfolioImage) -> None:
    process_vendor_portfolio_media_task.delay(str(image.id))


def _item(
    image: PortfolioImage,
    category: str,
    message: str,
    *,
    updated: bool = False,
    queued: bool = False,
) -> dict[str, Any]:
    return {
        "image_id": str(image.id),
        "vendor_id": str(image.vendor_id),
        "category": category,
        "message": message,
        "updated": updated,
        "queued": queued,
    }


def _is_complete(image: PortfolioImage, url: str | None) -> bool:
    return (
        bool(url)
        and image.upload_status == PortfolioImage.UploadStatus.UPLOADED
        and image.quality_status
        in {
            PortfolioImage.QualityStatus.PASSED,
            PortfolioImage.QualityStatus.NEEDS_MANUAL_REVIEW,
            PortfolioImage.QualityStatus.FAILED,
        }
    )


def _media_url(image: PortfolioImage) -> str | None:
    return _clean(image.cloudinary_secure_url) or _clean(image.secure_url)


def _cloudinary_public_id(image: PortfolioImage) -> str | None:
    return _clean(image.cloudinary_public_id) or _clean(image.public_id)


def _resource_type(image: PortfolioImage) -> str:
    return "video" if image.media_type == PortfolioImage.MediaType.VIDEO else "image"


def _temp_file_exists(path: str | None) -> bool:
    path = _clean(path)
    if not path:
        return False
    try:
        return default_storage.exists(path)
    except Exception:
        logger.exception("Portfolio temp-file existence check failed.", extra={"temp_upload_path": path})
        return False


def _delete_temp_file(path: str | None, *, image_id: str) -> None:
    path = _clean(path)
    if not path:
        return
    try:
        if default_storage.exists(path):
            default_storage.delete(path)
    except Exception:
        logger.warning("Failed to delete recovered portfolio temp file.", extra={"image_id": image_id})


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
