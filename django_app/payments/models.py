import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django_app.identity.models import User


class Payment(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        REFUND_REQUESTED = "refund_requested", "Refund Requested"
        REFUNDED = "refunded", "Refunded"

    class Method(models.TextChoices):
        CARD = "card", "Card"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"

    class Environment(models.TextChoices):
        TEST = "test", "Test"
        LIVE = "live", "Live"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="payments")
    amount_minor = models.PositiveBigIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100_000_000)]
    )
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    reference = models.CharField(max_length=50, unique=True, db_index=True)
    idempotency_key = models.CharField(max_length=50, unique=True, db_index=True)
    provider_reference = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    provider_reference_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    context_reference = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict)
    environment = models.CharField(max_length=10, choices=Environment.choices, default=Environment.TEST)
    dek_encrypted = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.amount_minor} {self.currency} ({self.status})"


class WebhookEvent(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        PROCESSED_SUCCESS = "processed_success", "Processed Success"
        REJECTED_UNKNOWN = "rejected_unknown", "Rejected Unknown"
        REJECTED_POLICY = "rejected_policy", "Rejected Policy"
        FRAUD_DETECTED = "fraud_detected", "Fraud Detected"
        LOCK_FAILED_RETRY = "lock_failed_retry", "Lock Failed Retry"
        VERIFY_FAILED_RETRY = "verify_failed_retry", "Verify Failed Retry"
        REJECTED_MISSING_REF = "rejected_missing_ref", "Rejected Missing Ref"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=100, unique=True, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=30, choices=Status.choices)
    dek_encrypted = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_id} - {self.status}"

class ApiKey(models.Model):
    class Scope(models.TextChoices):
        INITIATE_PAYMENT = "initiate_payment", "Initiate Payment"
        READ_STATUS = "read_status", "Read Status"
        FULL_ACCESS = "full_access", "Full Access"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key_id = models.CharField(max_length=64, unique=True, db_index=True)
    key_hash = models.CharField(max_length=128)
    secret_encrypted = models.JSONField(null=True, blank=True)
    secret_plain = models.CharField(max_length=128, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key_id} ({self.user.email})"

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=50)
    actor = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    dek_encrypted = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at}"