from celery import shared_task
from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter

@shared_task
def upload_portfolio_image_task(image_file, vendor_id):
    adapter = CloudinaryAdapter()
    result = adapter.upload_image(image_file)
    return result