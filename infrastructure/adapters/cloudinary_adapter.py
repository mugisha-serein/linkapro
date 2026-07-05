import logging
import os
import uuid

import cloudinary
import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


class CloudinaryAdapter:
    def __init__(self):
        self._cloudinary_configured = bool(
            settings.CLOUDINARY_CLOUD_NAME
            and settings.CLOUDINARY_API_KEY
            and settings.CLOUDINARY_API_SECRET
        )
        if self._cloudinary_configured:
            cloudinary.config(
                cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                api_key=settings.CLOUDINARY_API_KEY,
                api_secret=settings.CLOUDINARY_API_SECRET,
                secure=True,
            )

    def upload_image(self, file, folder: str = "vendor_portfolio", fallback_to_storage: bool = True) -> dict:
        if not self._cloudinary_configured:
            if not fallback_to_storage:
                raise RuntimeError("Cloudinary credentials are not configured.")
            logger.warning("Cloudinary credentials are not configured. Saving portfolio image locally instead.")
            return self._store_locally(file, folder)

        try:
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="image",
                allowed_formats=["jpg", "jpeg", "png", "webp"],
                max_file_size=10_000_000,  # 10MB
            )
        except cloudinary.exceptions.Error as exc:
            if not fallback_to_storage:
                raise
            logger.exception("Cloudinary upload failed; falling back to local storage: %s", exc)
            return self._store_locally(file, folder)

        return {
            "public_id": result["public_id"],
            "secure_url": result["secure_url"],
        }

    def _store_locally(self, file, folder: str = "vendor_portfolio") -> dict:
        extension = os.path.splitext(getattr(file, "name", "upload"))[1] or ""
        filename = f"{uuid.uuid4().hex}{extension}"
        relative_path = os.path.join(folder, filename).replace("\\", "/")
        saved_path = default_storage.save(relative_path, file)
        return {
            "public_id": saved_path,
            "secure_url": default_storage.url(saved_path),
        }

    def delete_image(self, public_id: str) -> bool:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"

    def upload_file(self, file_obj, folder: str = "exports", public_id: str = None, resource_type: str = "raw") -> dict:
        result = cloudinary.uploader.upload(
            file_obj,
            folder=folder,
            public_id=public_id,
            resource_type=resource_type,
            use_filename=True,
            unique_filename=False,
        )
        return {"public_id": result["public_id"], "secure_url": result["secure_url"]}

    def get_resource(self, public_id: str, resource_type: str = "image") -> dict | None:
        if not public_id:
            return None
        if not self._cloudinary_configured:
            raise RuntimeError("Cloudinary credentials are not configured.")

        try:
            return cloudinary.api.resource(public_id, resource_type=resource_type)
        except cloudinary.exceptions.Error as exc:
            if getattr(exc, "http_code", None) == 404 or exc.__class__.__name__.lower() == "notfound":
                return None
            logger.exception("Cloudinary resource lookup failed.", extra={"public_id": public_id})
            raise
