import uuid
import logging
from celery import shared_task
from django.template.loader import render_to_string
from weasyprint import HTML
import openpyxl
from openpyxl.styles import Font, PatternFill
from io import BytesIO
from django.conf import settings
from django.core.files.storage import default_storage

from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from infrastructure.repos.django_export_job_repository import DjangoExportJobRepository
from django_app.events.models import Event
from django_app.events.models import BudgetLine, GuestEntry, TimelineBlock
from django_app.vendors.models import VerificationDocument

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_pdf_task(self, job_id: str, event_id: str, export_type: str):
    """Generate PDF (event brief or timeline) and upload to Cloudinary."""
    repo = DjangoExportJobRepository()
    job = repo.get_by_id(uuid.UUID(job_id))
    if not job:
        return

    job.mark_processing()
    repo.save(job)

    try:
        event = Event.objects.select_related("planner").get(id=event_id)
        context = {"event": event}

        if export_type == "event_brief":
            context.update({
                "checklists": event.checklists.prefetch_related("items").all(),
                "budget_lines": event.budget_lines.all(),
                "guests": event.guests.all(),
            })
            html_string = render_to_string("exports/event_brief.html", context)
            filename = f"event_brief_{event.id}.pdf"
        else:  # timeline
            context["timeline_blocks"] = event.timeline_blocks.order_by("order")
            html_string = render_to_string("exports/timeline.html", context)
            filename = f"timeline_{event.id}.pdf"

        pdf_file = BytesIO()
        HTML(string=html_string).write_pdf(pdf_file)
        pdf_file.seek(0)

        adapter = CloudinaryAdapter()
        result = adapter.upload_file(pdf_file, folder="exports", public_id=filename.replace(".pdf", ""), resource_type="raw")
        file_url = result["secure_url"]

        job.complete(file_url)
        repo.save(job)

        # Send email notification (optional)
        # send_export_ready_email(job.requested_by.email, file_url)

    except Exception as e:
        job.fail(str(e))
        repo.save(job)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3)
def generate_excel_task(self, job_id: str, event_id: str, export_type: str):
    """Generate Excel (budget or guest list) and upload to Cloudinary."""
    repo = DjangoExportJobRepository()
    job = repo.get_by_id(uuid.UUID(job_id))
    if not job:
        return

    job.mark_processing()
    repo.save(job)

    try:
        event = Event.objects.get(id=event_id)
        wb = openpyxl.Workbook()
        ws = wb.active

        if export_type == "budget":
            ws.title = "Budget"
            headers = ["Category", "Description", "Estimated (RWF)", "Actual (RWF)", "Notes"]
            ws.append(headers)
            for line in event.budget_lines.all():
                ws.append([
                    line.get_category_display(),
                    line.description,
                    line.estimated_cost,
                    line.actual_cost or "",
                    line.notes or "",
                ])
            filename = f"budget_{event.id}.xlsx"
        else:  # guest_list
            ws.title = "Guest List"
            headers = ["Name", "Email", "Phone", "RSVP", "Dietary Restrictions", "Plus One", "Table", "Notes"]
            ws.append(headers)
            for guest in event.guests.all():
                ws.append([
                    guest.full_name,
                    guest.email or "",
                    guest.phone or "",
                    guest.get_rsvp_status_display(),
                    ", ".join(guest.dietary_restrictions),
                    "Yes" if guest.plus_one else "No",
                    guest.table_assignment or "",
                    guest.notes or "",
                ])
            filename = f"guest_list_{event.id}.xlsx"

        # Style headers
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

        excel_file = BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        adapter = CloudinaryAdapter()
        result = adapter.upload_file(excel_file, folder="exports", public_id=filename.replace(".xlsx", ""), resource_type="raw")
        file_url = result["secure_url"]

        job.complete(file_url)
        repo.save(job)

    except Exception as e:
        job.fail(str(e))
        repo.save(job)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, retry_backoff=True, retry_jitter=True)
def upload_vendor_verification_document_task(self, document_id: str):
    document = VerificationDocument.objects.select_related("vendor").get(id=uuid.UUID(str(document_id)))

    if (
        document.upload_status == VerificationDocument.UploadStatus.COMPLETED
        and (document.cloudinary_secure_url or document.secure_url)
    ):
        return {"status": "completed", "document_id": str(document.id)}

    if not document.temp_upload_path:
        _mark_document_upload_failed(document, "Uploaded document is no longer available.")
        return {"status": "failed", "document_id": str(document.id)}

    document.upload_status = VerificationDocument.UploadStatus.PROCESSING
    document.failure_reason = None
    document.save(update_fields=["upload_status", "failure_reason", "updated_at"])

    try:
        with default_storage.open(document.temp_upload_path, "rb") as upload_file:
            result = CloudinaryAdapter().upload_file(
                upload_file,
                folder="vendor_verification_documents",
                public_id=str(document.id),
                resource_type="raw",
            )
    except Exception as exc:
        safe_error = "Verification document upload failed. Please try again."
        _mark_document_upload_failed(document, safe_error)
        logger.exception("Vendor verification document upload failed.", extra={"document_id": str(document.id)})
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "document_id": str(document.id)}

    temp_upload_path = document.temp_upload_path
    document.cloudinary_public_id = result["public_id"]
    document.cloudinary_secure_url = result["secure_url"]
    document.secure_url = result["secure_url"]
    document.upload_status = VerificationDocument.UploadStatus.COMPLETED
    document.verification_status = VerificationDocument.VerificationStatus.PENDING_REVIEW
    document.fraud_status = VerificationDocument.FraudStatus.REVIEW_REQUIRED
    document.failure_reason = None
    document.temp_upload_path = None
    document.save(
        update_fields=[
            "cloudinary_public_id",
            "cloudinary_secure_url",
            "secure_url",
            "upload_status",
            "verification_status",
            "fraud_status",
            "failure_reason",
            "temp_upload_path",
            "updated_at",
        ]
    )

    try:
        if temp_upload_path and default_storage.exists(temp_upload_path):
            default_storage.delete(temp_upload_path)
    except Exception:
        logger.warning("Failed to delete temporary verification document.", extra={"document_id": str(document.id)})

    return {"status": "completed", "document_id": str(document.id)}


def _mark_document_upload_failed(document: VerificationDocument, message: str) -> None:
    document.upload_status = VerificationDocument.UploadStatus.FAILED
    document.verification_status = VerificationDocument.VerificationStatus.FAILED
    document.failure_reason = message
    document.save(update_fields=["upload_status", "verification_status", "failure_reason", "updated_at"])
