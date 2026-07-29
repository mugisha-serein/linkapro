# Generated manually after audit confirmed missing documents migrations.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("events", "0001_initial"),
        ("identity", "0003_user_totp_secret_user_two_factor_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExportJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "export_type",
                    models.CharField(
                        choices=[
                            ("event_brief", "Event Brief"),
                            ("timeline", "Timeline"),
                            ("budget", "Budget"),
                            ("guest_list", "Guest List"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("file_url", models.URLField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="export_jobs",
                        to="events.event",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="export_jobs",
                        to="identity.user",
                    ),
                ),
            ],
        ),
    ]
