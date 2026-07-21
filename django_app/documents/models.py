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


class DocumentDomainEventOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event_id = models.UUIDField(unique=True)
    aggregate_id = models.UUIDField(db_index=True)
    aggregate_version = models.PositiveIntegerField(default=0)
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="docs_event_status_next_idx"),
            models.Index(fields=["aggregate_id", "aggregate_version"], name="docs_event_aggregate_idx"),
        ]
