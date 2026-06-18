from django.core.management.base import BaseCommand, CommandError

from django_app.vendors.models import VerificationDocument
from tasks.document_tasks import process_vendor_verification_document_task


class Command(BaseCommand):
    help = "Queue or process deferred vendor verification documents."

    def add_arguments(self, parser):
        parser.add_argument("--process-inline", action="store_true", help="Process documents synchronously.")

    def handle(self, *args, **options):
        documents = VerificationDocument.objects.filter(
            upload_status__in=[
                VerificationDocument.UploadStatus.QUEUED,
                VerificationDocument.UploadStatus.PROCESSING_DEFERRED,
            ],
        ).exclude(temp_upload_path__isnull=True).exclude(temp_upload_path="")

        queued = 0
        processed = 0
        failed = 0
        for document in documents:
            if document.cloudinary_secure_url or document.secure_url:
                continue
            try:
                if options["process_inline"]:
                    process_vendor_verification_document_task.run(str(document.id))
                    processed += 1
                else:
                    process_vendor_verification_document_task.delay(str(document.id))
                    queued += 1
            except Exception:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Deferred vendor documents summary: queued={queued}, processed={processed}, failed={failed}"
            )
        )
        if failed:
            raise CommandError("One or more deferred vendor documents could not be queued or processed.")
