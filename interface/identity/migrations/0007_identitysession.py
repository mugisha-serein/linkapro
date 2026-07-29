# Generated manually for identity device/session tracking

import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0006_user_auth_token_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="IdentitySession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_family", models.CharField(db_index=True, max_length=36, unique=True)),
                ("device_label", models.CharField(blank=True, default="Unknown device", max_length=255)),
                ("user_agent_hash", models.CharField(blank=True, max_length=64, null=True)),
                ("ip_hash", models.CharField(blank=True, max_length=64, null=True)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_seen_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("revoked_reason", models.CharField(blank=True, max_length=255)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identity_sessions",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "revoked_at", "last_seen_at"], name="identity_id_user_id_1c7d2b_idx"),
                    models.Index(fields=["user", "created_at"], name="identity_id_user_id_55ef56_idx"),
                ],
            },
        ),
    ]
