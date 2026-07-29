from django.dispatch import receiver
from infrastructure.adapters.django_event_dispatcher import export_requested
from tasks.document_tasks import generate_pdf_task, generate_excel_task


@receiver(export_requested)
def handle_export_requested(sender, event, **kwargs):
    job = event
    if job.export_type.value in ["event_brief", "timeline"]:
        generate_pdf_task.delay(str(job.id), str(job.event_id), job.export_type.value)
    else:
        generate_excel_task.delay(str(job.id), str(job.event_id), job.export_type.value)