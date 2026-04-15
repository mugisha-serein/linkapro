from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


class UserSession(models.Model):
    """
    Central security orchestrator for authentication lifecycle.

    Responsibilities:
    - session lifecycle tracking
    - JWT refresh binding
    - device association
    - anomaly state tracking
    """

    class SessionState(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"
        SUSPICIOUS = "SUSPICIOUS", "Suspicious"
        LOCKED = "LOCKED", "Locked"

    # -------------------------
    # IDENTITY
    # -------------------------
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    device = models.ForeignKey(
        "accounts.DeviceFingerprint",
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    # -------------------------
    # SESSION CORE
    # -------------------------
    session_key = models.CharField(max_length=255, unique=True)

    # JWT rotation tracking
    refresh_token_jti = models.CharField(max_length=255, db_index=True)
    previous_refresh_token_jti = models.CharField(max_length=255, null=True, blank=True)

    # JWT family binding (CRITICAL FIX)
    family_id = models.UUIDField(db_index=True)

    # -------------------------
    # NETWORK SECURITY
    # -------------------------
    ip_address = models.GenericIPAddressField()
    last_ip_address = models.GenericIPAddressField(null=True, blank=True)

    user_agent = models.TextField()

    # -------------------------
    # STATE MANAGEMENT (UPGRADED)
    # -------------------------
    state = models.CharField(
        max_length=20,
        choices=SessionState.choices,
        default=SessionState.ACTIVE,
        db_index=True,
    )

    # -------------------------
    # LIFECYCLE
    # -------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(default=timezone.now)

    expires_at = models.DateTimeField(db_index=True)

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, null=True, blank=True)

    # -------------------------
    # SECURITY SIGNALS
    # -------------------------
    risk_score = models.PositiveSmallIntegerField(default=0)
    anomaly_detected = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_user_session"
        ordering = ("-created_at",)

        indexes = [
            models.Index(fields=["user", "state"], name="accounts_session_user_state_idx"),
            models.Index(fields=["expires_at"], name="accounts_session_expiry_idx"),
            models.Index(fields=["refresh_token_jti"], name="accounts_session_jti_idx"),
            models.Index(fields=["family_id"], name="accounts_session_family_idx"),
            models.Index(fields=["device", "user"], name="accounts_session_device_user_idx"),
        ]