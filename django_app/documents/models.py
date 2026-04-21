import uuid
from django.db import models
from django.utils import timezone
from django_app.identity.models import User
from django_app.events.models import Event


class ExportJob(models.Model):
    class ExportType(models.TextChoices):
        EVENT_BRIEF = "event_brief"
        TIMELINE = "timeline"
        BUDGET = "budget"
        GUEST_LIST = "guest_list"

    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="export_jobs")
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="export_jobs")
    export_type = models.CharField(max_length=20, choices=ExportType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.export_type} for {self.event.name} ({self.status})"