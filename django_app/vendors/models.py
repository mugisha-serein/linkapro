import uuid
from django.db import models
from django.utils import timezone
from django_app.identity.models import User

class VendorProfile(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        PENDING_REVIEW = "pending_review"
        APPROVED = "approved"
        REJECTED = "rejected"
        SUSPENDED = "suspended"

    class Category(models.TextChoices):
        PHOTOGRAPHY = "photography"
        CATERING = "catering"
        DECOR = "decor"
        VENUE = "venue"
        ENTERTAINMENT = "entertainment"
        TRANSPORTATION = "transportation"
        ATTIRE = "attire"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
    business_name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=Category.choices)
    custom_category = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField()
    service_area = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30)
    website = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name

    @classmethod
    def required_profile_fields(cls) -> tuple[str, ...]:
        return (
            "business_name",
            "category",
            "description",
            "service_area",
            "contact_email",
            "contact_phone",
        )

    def get_profile_completion_errors(self) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}
        for field_name in self.required_profile_fields():
            value = getattr(self, field_name, None)
            if value is None or not str(value).strip():
                errors[field_name] = ["This field is required."]
        if self.description and len(self.description.strip()) < 20:
            errors["description"] = ["Use at least 20 characters for your description."]
        if self.category == self.Category.OTHER and not (self.custom_category or "").strip():
            errors["custom_category"] = ["Describe what you do when category is Other."]
        return errors

    @property
    def is_profile_complete(self) -> bool:
        return not self.get_profile_completion_errors()

    def can_access_vendor_workspace(self) -> bool:
        return self.status != self.Status.DRAFT and self.is_profile_complete


class PortfolioImage(models.Model):
    class UploadStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="images")
    public_id = models.CharField(max_length=200, blank=True)
    secure_url = models.URLField(blank=True)
    caption = models.CharField(max_length=500, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    upload_status = models.CharField(max_length=20, choices=UploadStatus.choices, default=UploadStatus.COMPLETED)
    upload_error = models.TextField(blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    temp_upload_path = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Image {self.order} for {self.vendor.business_name}"


class ServicePackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="packages")
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="RWF")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.vendor.business_name}"


class Inquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="inquiries")
    client_name = models.CharField(max_length=200)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=30, blank=True, null=True)
    message = models.TextField()
    event_date = models.DateField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Inquiry from {self.client_name} to {self.vendor.business_name}"


class VerificationDocument(models.Model):
    class DocumentType(models.TextChoices):
        BUSINESS_REGISTRATION = "business_registration", "Business Registration"
        TAX_CERTIFICATE = "tax_certificate", "Tax Certificate"
        TRADE_LICENSE = "trade_license", "Trade License"
        OWNER_ID = "owner_id", "Owner ID"
        OTHER = "other", "Other"

    class FraudStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PASSED = "passed", "Passed"
        REVIEW_REQUIRED = "review_required", "Review Required"
        REJECTED = "rejected", "Rejected"

    class UploadStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        PROCESSING_DEFERRED = "processing_deferred", "Processing Deferred"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class VerificationStatus(models.TextChoices):
        PENDING_REVIEW = "pending_review", "Pending Review"
        NEEDS_MANUAL_REVIEW = "needs_manual_review", "Needs Manual Review"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="verification_documents")
    document_type = models.CharField(max_length=40, choices=DocumentType.choices)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    secure_url = models.URLField(blank=True)
    cloudinary_public_id = models.CharField(max_length=255, blank=True, null=True)
    cloudinary_secure_url = models.URLField(blank=True, null=True)
    upload_status = models.CharField(max_length=20, choices=UploadStatus.choices, default=UploadStatus.PENDING)
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING_REVIEW,
    )
    failure_reason = models.TextField(blank=True, null=True)
    temp_upload_path = models.CharField(max_length=500, blank=True, null=True)
    odcr_status = models.CharField(max_length=40, blank=True, null=True)
    odcr_score = models.PositiveSmallIntegerField(blank=True, null=True)
    odcr_result_summary = models.TextField(blank=True, null=True)
    fraud_status = models.CharField(max_length=20, choices=FraudStatus.choices, default=FraudStatus.PENDING)
    fraud_score = models.PositiveSmallIntegerField(default=0)
    fraud_reasons = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document_type} for {self.vendor.business_name}"
