from __future__ import annotations

import uuid
from django.db import models
from django.utils import timezone


class LoginActivity(models.Model):
    """
    Security telemetry log for authentication events.

    Used for:
    - anomaly detection
    - brute-force detection
    - behavioral analytics
    - forensic auditing
    """

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        BLOCKED = "BLOCKED", "Blocked"

    class EventType(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        PASSWORD_ATTEMPT = "PASSWORD_ATTEMPT", "Password Attempt"
        TOKEN_REFRESH = "TOKEN_REFRESH", "Token Refresh"
        LOGOUT = "LOGOUT", "Logout"
        SUSPICIOUS = "SUSPICIOUS", "Suspicious Activity"

    # -------------------------
    # IDENTITY
    # -------------------------
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # correlation for attack tracing (CRITICAL FIX)
    correlation_id = models.UUIDField(db_index=True, default=uuid.uuid4)

    # event fingerprint (dedup + forensic integrity)
    event_hash = models.CharField(max_length=128, unique=True, db_index=True)

    # -------------------------
    # RELATIONS
    # -------------------------
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="login_activities",
        db_index=True,
    )

    session = models.ForeignKey(
        "accounts.UserSession",
        on_delete=models.SET_NULL,
        related_name="login_activities",
        null=True,
        blank=True,
    )

    device = models.ForeignKey(
        "accounts.DeviceFingerprint",
        on_delete=models.SET_NULL,
        related_name="login_activities",
        null=True,
        blank=True,
    )

    # -------------------------
    # NETWORK SIGNALS (NORMALIZED)
    # -------------------------
    ip_hash = models.CharField(max_length=128, db_index=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)

    user_agent = models.TextField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)

    # -------------------------
    # EVENT CLASSIFICATION
    # -------------------------
    status = models.CharField(max_length=20, choices=Status.choices)
    event_type = models.CharField(max_length=30, choices=EventType.choices, default=EventType.LOGIN)

    failure_reason = models.TextField(blank=True, null=True)

    # -------------------------
    # SECURITY SIGNALS (CRITICAL ADDITION)
    # -------------------------
    risk_score = models.PositiveSmallIntegerField(default=0)
    anomaly_flag = models.BooleanField(default=False)

    # -------------------------
    # TIMING / BEHAVIORAL SIGNALS
    # -------------------------
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    attempt_sequence = models.PositiveIntegerField(default=1)

    # -------------------------
    # LIFECYCLE
    # -------------------------
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_login_activity"
        ordering = ("-created_at",)

        indexes = [
            models.Index(fields=["user", "created_at"], name="login_activity_user_time_idx"),
            models.Index(fields=["status", "created_at"], name="login_activity_status_time_idx"),
            models.Index(fields=["ip_hash", "created_at"], name="login_activity_ip_time_idx"),
            models.Index(fields=["correlation_id"], name="login_activity_corr_idx"),
            models.Index(fields=["event_type", "created_at"], name="login_activity_event_time_idx"),
        ]