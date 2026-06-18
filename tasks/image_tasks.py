import logging
import uuid

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import transaction

from django_app.vendors.models import PortfolioImage
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from infrastructure.adapters.media_quality_analyzer import MediaQualityAnalyzer

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True)
def process_vendor_portfolio_media_task(self, image_id: str):
    image_uuid = uuid.UUID(str(image_id))
    image = PortfolioImage.objects.select_related("vendor").get(id=image_uuid)

    if (
        image.upload_status == PortfolioImage.UploadStatus.UPLOADED
        and (image.cloudinary_secure_url or image.secure_url)
        and image.quality_status
        in (
            PortfolioImage.QualityStatus.PASSED,
            PortfolioImage.QualityStatus.NEEDS_MANUAL_REVIEW,
            PortfolioImage.QualityStatus.FAILED,
        )
    ):
        return {"status": "completed", "image_id": str(image.id)}

    if not image.temp_upload_path:
        _mark_failed(image, "Uploaded media is no longer available.")
        return {"status": "failed", "image_id": str(image.id)}

    with transaction.atomic():
        image.upload_status = PortfolioImage.UploadStatus.PROCESSING
        image.upload_error = None
        image.failure_reason = None
        image.save(update_fields=["upload_status", "upload_error", "failure_reason", "updated_at"])

    quality_result = MediaQualityAnalyzer().analyze(storage_path=image.temp_upload_path, media_type=image.media_type)
    image.quality_status = _quality_status_for_result(quality_result.status)
    image.analyzer_score = quality_result.score
    image.analyzer_summary = quality_result.summary
    if quality_result.width:
        image.width = quality_result.width
    if quality_result.height:
        image.height = quality_result.height
    if quality_result.duration_seconds:
        image.duration_seconds = quality_result.duration_seconds

    try:
        with default_storage.open(image.temp_upload_path, "rb") as upload_file:
            if image.media_type == PortfolioImage.MediaType.IMAGE:
                result = CloudinaryAdapter().upload_image(upload_file, fallback_to_storage=False)
            else:
                result = CloudinaryAdapter().upload_file(
                    upload_file,
                    folder="vendor_portfolio",
                    public_id=str(image.id),
                    resource_type="video",
                )
    except Exception as exc:
        safe_error = "Portfolio media upload failed. Please try again."
        _mark_failed(image, safe_error)
        logger.exception("Vendor portfolio media upload failed.", extra={"image_id": str(image.id)})
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "image_id": str(image.id)}

    temp_upload_path = image.temp_upload_path
    image.public_id = result["public_id"]
    image.secure_url = result["secure_url"]
    image.cloudinary_public_id = result["public_id"]
    image.cloudinary_secure_url = result["secure_url"]
    image.upload_status = PortfolioImage.UploadStatus.UPLOADED
    image.visibility_status = (
        PortfolioImage.VisibilityStatus.WAITING_APPROVAL
        if image.quality_status == PortfolioImage.QualityStatus.PASSED
        else PortfolioImage.VisibilityStatus.PRIVATE
    )
    image.upload_error = None
    image.failure_reason = None
    image.temp_upload_path = None
    image.save(
        update_fields=[
            "public_id",
            "secure_url",
            "cloudinary_public_id",
            "cloudinary_secure_url",
            "upload_status",
            "quality_status",
            "visibility_status",
            "upload_error",
            "failure_reason",
            "temp_upload_path",
            "width",
            "height",
            "duration_seconds",
            "analyzer_score",
            "analyzer_summary",
            "updated_at",
        ]
    )

    try:
        if temp_upload_path and default_storage.exists(temp_upload_path):
            default_storage.delete(temp_upload_path)
    except Exception:
        logger.warning("Failed to delete temporary portfolio upload.", extra={"image_id": str(image.id)})

    return {"status": "completed", "image_id": str(image.id)}


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True)
def upload_vendor_portfolio_image_task(self, image_id: str):
    return process_vendor_portfolio_media_task.run(image_id)


@shared_task
def upload_portfolio_image_task(image_file, vendor_id):
    raise RuntimeError("Direct file-object portfolio uploads are disabled. Use process_vendor_portfolio_media_task.")


def _mark_failed(image: PortfolioImage, message: str) -> None:
    image.upload_status = PortfolioImage.UploadStatus.FAILED
    image.upload_error = message
    image.failure_reason = message
    image.visibility_status = PortfolioImage.VisibilityStatus.PRIVATE
    image.save(update_fields=["upload_status", "upload_error", "failure_reason", "visibility_status", "updated_at"])


def _quality_status_for_result(status: str) -> str:
    normalized = (status or "").lower()
    if normalized == "passed":
        return PortfolioImage.QualityStatus.PASSED
    if normalized == "failed":
        return PortfolioImage.QualityStatus.FAILED
    return PortfolioImage.QualityStatus.NEEDS_MANUAL_REVIEW
