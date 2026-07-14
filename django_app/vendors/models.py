from datetime import timedelta
import uuid
from django.db import models
from django.db.models import Max, Q
from django.utils import timezone
from django_app.common.models import SoftDeleteModel
from django_app.identity.models import User
from domain.vendors.profile.entity import VendorProfile as DomainVendorProfile
from domain.vendors.profile.entity import profile_completion_errors_for

VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS = 15


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
    profile_image_url = models.URLField(blank=True, null=True)
    profile_image_public_id = models.CharField(max_length=255, blank=True, null=True)
    cover_image_url = models.URLField(blank=True, null=True)
    cover_image_public_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        now = timezone.now()
        changed_fields = set()
        if self.status == self.Status.PENDING_REVIEW and self.submitted_at is None:
            self.submitted_at = now
            changed_fields.add("submitted_at")
        if self.status == self.Status.APPROVED:
            if self.submitted_at is None:
                self.submitted_at = now
                changed_fields.add("submitted_at")
            if self.approved_at is None:
                self.approved_at = now
                changed_fields.add("approved_at")
            self.rejected_at = None
            self.rejection_reason = None
            changed_fields.update({"rejected_at", "rejection_reason"})
        if self.status == self.Status.REJECTED and self.rejected_at is None:
            self.rejected_at = now
            changed_fields.add("rejected_at")
        if kwargs.get("update_fields") is not None and changed_fields:
            kwargs["update_fields"] = tuple(set(kwargs["update_fields"]) | changed_fields)
        super().save(*args, **kwargs)

    @classmethod
    def required_profile_fields(cls) -> tuple[str, ...]:
        return DomainVendorProfile.required_profile_fields()

    def get_profile_completion_errors(self) -> dict[str, list[str]]:
        return profile_completion_errors_for(self, self.required_profile_fields())

    @property
    def is_profile_complete(self) -> bool:
        return not self.get_profile_completion_errors()

    def can_access_vendor_workspace(self) -> bool:
        return self.status != self.Status.DRAFT and self.is_profile_complete


class VendorProfileViewed(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="profile_view_counts")
    view_date = models.DateField()
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vendors_profile_view_logged"
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "view_date"],
                name="vendors_profile_view_logged_vendor_date_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["vendor", "view_date"], name="vendors_profile_view_logged_idx"),
        ]

    def __str__(self):
        return f"{self.vendor_id} viewed on {self.view_date}: {self.view_count}"


class PortfolioImage(SoftDeleteModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class UploadStatus(models.TextChoices):
        STAGED = "staged", "Staged"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING_DEFERRED = "processing_deferred", "Processing Deferred"
        FAILED = "failed", "Failed"

    class QualityStatus(models.TextChoices):
        PENDING_ANALYSIS = "pending_analysis", "Pending Analysis"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        NEEDS_MANUAL_REVIEW = "needs_manual_review", "Needs Manual Review"

    class VisibilityStatus(models.TextChoices):
        PRIVATE = "private", "Private"
        WAITING_APPROVAL = "waiting_approval", "Waiting Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="images")
    public_id = models.CharField(max_length=200, blank=True)
    secure_url = models.URLField(blank=True)
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE)
    caption = models.CharField(max_length=500, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    upload_status = models.CharField(max_length=30, choices=UploadStatus.choices, default=UploadStatus.UPLOADED)
    quality_status = models.CharField(
        max_length=30,
        choices=QualityStatus.choices,
        default=QualityStatus.PASSED,
    )
    visibility_status = models.CharField(
        max_length=30,
        choices=VisibilityStatus.choices,
        default=VisibilityStatus.APPROVED,
    )
    upload_error = models.TextField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    temp_upload_path = models.CharField(max_length=500, blank=True, null=True)
    local_preview_url = models.URLField(blank=True, null=True)
    cloudinary_public_id = models.CharField(max_length=255, blank=True, null=True)
    cloudinary_secure_url = models.URLField(blank=True, null=True)
    width = models.PositiveIntegerField(blank=True, null=True)
    height = models.PositiveIntegerField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    analyzer_score = models.PositiveSmallIntegerField(blank=True, null=True)
    analyzer_summary = models.TextField(blank=True, null=True)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "order"],
                condition=Q(is_active=True, is_deleted=False),
                name="vendors_portfolio_active_order_unique",
            ),
        ]

    def __str__(self):
        return f"Image {self.order} for {self.vendor.business_name}"

    def save(self, *args, **kwargs):
        if self.is_active and not self.is_deleted and self.vendor_id:
            conflict = (
                PortfolioImage.all_objects.filter(
                    vendor_id=self.vendor_id,
                    order=self.order,
                    is_active=True,
                    is_deleted=False,
                )
                .exclude(id=self.id)
                .exists()
            )
            if conflict:
                max_order = (
                    PortfolioImage.all_objects.filter(
                        vendor_id=self.vendor_id,
                        is_active=True,
                        is_deleted=False,
                    ).aggregate(Max("order"))["order__max"]
                )
                self.order = (max_order if max_order is not None else -1) + 1
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = tuple(set(kwargs["update_fields"]) | {"order"})
        super().save(*args, **kwargs)


class ServicePackage(SoftDeleteModel):
    class PackageTier(models.TextChoices):
        STANDARD = "standard", "Standard"
        PREMIER = "premier", "Premier"
        GOLD = "gold", "Gold"

    class ApprovalStatus(models.TextChoices):
        WAITING_APPROVAL = "waiting_approval", "Waiting Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="packages")
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="RWF", choices=[("RWF", "RWF")])
    package_tier = models.CharField(max_length=20, choices=PackageTier.choices, default=PackageTier.STANDARD)
    approval_status = models.CharField(
        max_length=30,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.WAITING_APPROVAL,
    )
    rejection_reason = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    last_approved_at = models.DateTimeField(null=True, blank=True)
    last_vendor_public_edit_at = models.DateTimeField(null=True, blank=True)
    next_vendor_edit_allowed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(currency="RWF"), name="vendors_servicepackage_currency_rwf"),
            models.CheckConstraint(
                condition=Q(is_deleted=False) | Q(is_active=False),
                name="vendors_servicepackage_deleted_inactive",
            ),
            models.CheckConstraint(
                condition=Q(is_deleted=False) | Q(deleted_at__isnull=False),
                name="vendors_servicepackage_deleted_at_required",
            ),
            models.CheckConstraint(
                condition=~Q(approval_status="waiting_approval") | Q(is_active=False),
                name="vendors_servicepackage_waiting_inactive",
            ),
            models.CheckConstraint(
                condition=~Q(approval_status="approved") | Q(last_approved_at__isnull=False),
                name="vendors_servicepackage_approved_at_required",
            ),
            models.CheckConstraint(
                condition=~Q(approval_status="rejected") | Q(is_active=False),
                name="vendors_servicepackage_rejected_inactive",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(approval_status="rejected")
                    | (Q(rejection_reason__isnull=False) & ~Q(rejection_reason=""))
                ),
                name="vendors_servicepackage_rejected_reason_required",
            ),
            models.CheckConstraint(
                condition=(
                    Q(approval_status="rejected")
                    | Q(rejection_reason__isnull=True)
                    | Q(rejection_reason="")
                ),
                name="vendors_servicepackage_rejection_only_rejected",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.vendor.business_name}"

    def save(self, *args, **kwargs):
        changed_fields = set()
        if self.approval_status == self.ApprovalStatus.APPROVED:
            approved_at = self.last_approved_at or timezone.now()
            if self.last_approved_at is None:
                self.last_approved_at = approved_at
                changed_fields.add("last_approved_at")
            if self.next_vendor_edit_allowed_at is None:
                self.next_vendor_edit_allowed_at = approved_at + self.vendor_edit_cooldown_delta()
                changed_fields.add("next_vendor_edit_allowed_at")
            if self.rejection_reason is not None:
                self.rejection_reason = None
                changed_fields.add("rejection_reason")
        if kwargs.get("update_fields") is not None and changed_fields:
            kwargs["update_fields"] = tuple(set(kwargs["update_fields"]) | changed_fields)
        super().save(*args, **kwargs)

    @staticmethod
    def vendor_edit_cooldown_delta() -> timedelta:
        return timedelta(days=VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS)

    def approve(self):
        approved_at = timezone.now()
        self.approval_status = self.ApprovalStatus.APPROVED
        self.rejection_reason = None
        self.is_active = True
        self.last_approved_at = approved_at
        self.next_vendor_edit_allowed_at = approved_at + self.vendor_edit_cooldown_delta()
        self.save(
            update_fields=[
                "approval_status",
                "rejection_reason",
                "is_active",
                "last_approved_at",
                "next_vendor_edit_allowed_at",
                "updated_at",
            ]
        )

    def reject(self, reason: str):
        self.approval_status = self.ApprovalStatus.REJECTED
        self.rejection_reason = reason
        self.is_active = False
        self.save(update_fields=["approval_status", "rejection_reason", "is_active", "updated_at"])


class Inquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name="inquiries")
    client_name = models.CharField(max_length=200)
    client_email = models.EmailField()
    client_phone = models.CharField(max_length=30, blank=True, null=True)
    message = models.TextField()
    event_date = models.DateField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
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


class VendorIdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    scope = models.CharField(max_length=120)
    actor_id = models.UUIDField(null=True, blank=True)
    key = models.CharField(max_length=200)
    payload_fingerprint = models.CharField(max_length=128)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    result = models.JSONField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "actor_id", "key"],
                name="vendors_idempotency_scope_actor_key_unique",
            ),
        ]


class VendorDomainEventOutbox(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event_id = models.UUIDField(unique=True)
    aggregate_id = models.UUIDField(db_index=True)
    aggregate_version = models.PositiveIntegerField()
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
            models.Index(fields=["status", "next_attempt_at"], name="vendors_event_status_next_idx"),
            models.Index(fields=["aggregate_id", "aggregate_version"], name="vendors_event_aggregate_idx"),
        ]
