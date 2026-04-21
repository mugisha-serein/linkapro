import uuid
from celery import shared_task
from django.template.loader import render_to_string
from weasyprint import HTML
import openpyxl
from openpyxl.styles import Font, PatternFill
from io import BytesIO
from django.conf import settings

from infrastructure.adapters.cloudinary_adapter import CloudinaryAdapter
from infrastructure.repos.django_export_job_repository import DjangoExportJobRepository
from django_app.events.models import Event
from django_app.events.models import BudgetLine, GuestEntry, TimelineBlock


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