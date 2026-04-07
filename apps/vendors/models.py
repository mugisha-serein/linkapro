from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

class VendorProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        NEEDS_REVISION = 'needs_revision', 'Needs Revision'
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=255, blank=True)
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT)
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def is_active(self):
        return self.approval_status == self.ApprovalStatus.APPROVED and self.user.is_active

    def submit_for_review(self):
        if self.approval_status == self.ApprovalStatus.DRAFT:
            self.approval_status = self.ApprovalStatus.PENDING_REVIEW
            self.save()

    def __str__(self):
        return f"Vendor Profile for {self.user.email}"
