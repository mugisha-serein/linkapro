import cloudinary
import cloudinary.uploader
from django.conf import settings

class CloudinaryAdapter:
    def __init__(self):
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )

    def upload_image(self, file, folder: str = "vendor_portfolio") -> dict:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png", "webp"],
            max_file_size=10_000_000  # 10MB
        )
        return {
            "public_id": result["public_id"],
            "secure_url": result["secure_url"]
        }

    def delete_image(self, public_id: str) -> bool:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"