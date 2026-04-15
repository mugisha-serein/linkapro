from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


class DeviceFingerprint(models.Model):
    """
    Security-grade device identity record.

    Stores hashed device identity + stable metadata snapshot.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="device_fingerprints",
    )

    # -------------------------
    # CORE IDENTITY (IMMUTABLE CONTRACT)
    # -------------------------
    fingerprint_hash = models.CharField(max_length=255, db_index=True)

    # -------------------------
    # STABLE DEVICE ATTRIBUTES (SNAPSHOT ONLY)
    # -------------------------
    user_agent = models.TextField(blank=True, default="")
    device_type = models.CharField(max_length=50, blank=True, default="")
    browser = models.CharField(max_length=100, blank=True, default="")
    os = models.CharField(max_length=100, blank=True, default="")
    timezone = models.CharField(max_length=100, blank=True, default="")
    language = models.CharField(max_length=20, blank=True, default="")

    # -------------------------
    # NETWORK SIGNAL (NORMALIZED, NOT RAW IP)
    # -------------------------
    ip_cidr = models.CharField(max_length=64, blank=True, default="")

    # -------------------------
    # ADVANCED FINGERPRINT SIGNALS
    # -------------------------
    canvas_hash = models.CharField(max_length=255, null=True, blank=True)
    webgl_hash = models.CharField(max_length=255, null=True, blank=True)

    # -------------------------
    # TRUST STATE
    # -------------------------
    is_trusted = models.BooleanField(default=False)

    # -------------------------
    # SESSION BINDING (CRITICAL MISSING PIECE FIXED)
    # -------------------------
    last_session_key = models.CharField(max_length=255, null=True, blank=True)
    last_family_id = models.UUIDField(null=True, blank=True)

    # -------------------------
    # TIMESTAMPS
    # -------------------------
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_device_fingerprint"
        ordering = ("-last_seen_at",)

        constraints = [
            models.UniqueConstraint(
                fields=["user", "fingerprint_hash"],
                name="accounts_device_fingerprint_user_hash_uniq",
            ),
        ]

        indexes = [
            models.Index(fields=["fingerprint_hash"], name="accounts_device_fp_hash_idx"),
            models.Index(fields=["user", "last_seen_at"], name="accounts_device_fp_seen_idx"),
            models.Index(fields=["user", "fingerprint_hash"], name="accounts_device_fp_user_hash_idx"),
        ]