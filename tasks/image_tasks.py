import logging
import uuid

from celery import shared_task
from django.core.files.storage import default_storage
from django.db import transaction

from django_app.vendors.models import PortfolioImage
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True)
def upload_vendor_portfolio_image_task(self, image_id: str):
    image_uuid = uuid.UUID(str(image_id))
    image = PortfolioImage.objects.select_related("vendor").get(id=image_uuid)

    if image.upload_status == PortfolioImage.UploadStatus.COMPLETED and image.secure_url:
        return {"status": "completed", "image_id": str(image.id)}

    if not image.temp_upload_path:
        _mark_failed(image, "Uploaded file is no longer available.")
        return {"status": "failed", "image_id": str(image.id)}

    with transaction.atomic():
        image.upload_status = PortfolioImage.UploadStatus.PROCESSING
        image.upload_error = None
        image.save(update_fields=["upload_status", "upload_error"])

    try:
        with default_storage.open(image.temp_upload_path, "rb") as upload_file:
            result = CloudinaryAdapter().upload_image(upload_file, fallback_to_storage=False)
    except Exception as exc:
        safe_error = "Portfolio image upload failed. Please try again."
        _mark_failed(image, safe_error)
        logger.exception("Vendor portfolio image upload failed.", extra={"image_id": str(image.id)})
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "image_id": str(image.id)}

    temp_upload_path = image.temp_upload_path
    image.public_id = result["public_id"]
    image.secure_url = result["secure_url"]
    image.upload_status = PortfolioImage.UploadStatus.COMPLETED
    image.upload_error = None
    image.temp_upload_path = None
    image.save(update_fields=["public_id", "secure_url", "upload_status", "upload_error", "temp_upload_path"])

    try:
        if temp_upload_path and default_storage.exists(temp_upload_path):
            default_storage.delete(temp_upload_path)
    except Exception:
        logger.warning("Failed to delete temporary portfolio upload.", extra={"image_id": str(image.id)})

    return {"status": "completed", "image_id": str(image.id)}


@shared_task
def upload_portfolio_image_task(image_file, vendor_id):
    raise RuntimeError("Direct file-object portfolio uploads are disabled. Use upload_vendor_portfolio_image_task.")


def _mark_failed(image: PortfolioImage, message: str) -> None:
    image.upload_status = PortfolioImage.UploadStatus.FAILED
    image.upload_error = message
    image.save(update_fields=["upload_status", "upload_error"])
