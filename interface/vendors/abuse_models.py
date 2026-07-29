from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class InquiryAbuseRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester_identity = models.UUIDField(db_index=True)
    vendor = models.ForeignKey(
        "vendors.VendorProfile",
        on_delete=models.CASCADE,
        related_name="inquiry_abuse_records",
    )
    payload_digest = models.CharField(max_length=64)
    duplicate_window_key = models.BigIntegerField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = "vendors"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "requester_identity",
                    "vendor",
                    "payload_digest",
                    "duplicate_window_key",
                ],
                name="vendors_inquiry_abuse_duplicate_window_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["requester_identity", "vendor", "created_at"],
                name="vendors_inquiry_abuse_rate_idx",
            ),
        ]
