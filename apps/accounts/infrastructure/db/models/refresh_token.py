# No Business Logic Here
import uuid

from django.db import models


class RefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
    )
    session = models.ForeignKey(
        "accounts.UserSession",
        on_delete=models.SET_NULL,
        related_name="refresh_tokens",
        blank=True,
        null=True,
    )

    jti = models.CharField(max_length=255, unique=True, db_index=True)
    token_hash = models.CharField(max_length=255, unique=True)
    family_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    parent_jti = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    replaced_by_jti = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(blank=True, null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_refresh_token"
        ordering = ("-issued_at",)
        indexes = [
            models.Index(fields=["user", "expires_at"], name="accounts_refresh_token_user_exp_idx"),
            models.Index(fields=["session", "expires_at"], name="accounts_refresh_token_session_exp_idx"),
            models.Index(fields=["family_id"], name="accounts_refresh_token_family_idx"),
        ]
