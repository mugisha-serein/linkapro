import uuid
from django.db import models
from django.utils import timezone
from django_app.identity.models import User


class AuditLog(models.Model):
    class ActionType(models.TextChoices):
        APPROVE_VENDOR = "approve_vendor"
        REJECT_VENDOR = "reject_vendor"
        SUSPEND_VENDOR = "suspend_vendor"
        BAN_USER = "ban_user"
        SUSPEND_USER = "suspend_user"
        REINSTATE_USER = "reinstate_user"
        DELETE_CONTENT = "delete_content"
        FLAG_RESOLVE = "flag_resolve"
        APPROVE_PACKAGE = "approve_package"
        REJECT_PACKAGE = "reject_package"
        HARD_DELETE_PACKAGE = "hard_delete_package"
        APPROVE_PORTFOLIO_MEDIA = "approve_portfolio_media"
        REJECT_PORTFOLIO_MEDIA = "reject_portfolio_media"
        HARD_DELETE_PORTFOLIO_MEDIA = "hard_delete_portfolio_media"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="admin_actions")
    action_type = models.CharField(max_length=40, choices=ActionType.choices)
    target_type = models.CharField(max_length=50)
    target_id = models.UUIDField()
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.admin.email if self.admin else 'System'} - {self.action_type} on {self.target_type}"


class ContentFlag(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        REVIEWED = "reviewed"
        DISMISSED = "dismissed"

    class ContentType(models.TextChoices):
        VENDOR_PROFILE = "vendor_profile"
        REVIEW = "review"
        PORTFOLIO_IMAGE = "portfolio_image"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="flags_reported")
    content_type = models.CharField(max_length=30, choices=ContentType.choices)
    content_id = models.UUIDField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Flag on {self.content_type} ({self.status})"


class PlatformMetric(models.Model):
    date = models.DateField(unique=True)
    total_users = models.PositiveIntegerField(default=0)
    total_planners = models.PositiveIntegerField(default=0)
    total_vendors = models.PositiveIntegerField(default=0)
    active_vendors = models.PositiveIntegerField(default=0)
    pending_vendor_approvals = models.PositiveIntegerField(default=0)
    total_events = models.PositiveIntegerField(default=0)
    total_inquiries = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Metrics for {self.date}"
