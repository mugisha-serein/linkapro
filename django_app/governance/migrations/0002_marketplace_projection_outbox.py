import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketplaceProjectionOutbox",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("upsert_vendor", "Upsert Vendor"),
                            ("delete_vendor", "Delete Vendor"),
                        ],
                        max_length=40,
                    ),
                ),
                ("vendor_id", models.UUIDField(db_index=True)),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("delivered", "Delivered"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["status", "next_attempt_at"], name="governance__status_0ee9bb_idx"),
                    models.Index(fields=["vendor_id", "created_at"], name="governance__vendor__f42562_idx"),
                ],
            },
        ),
    ]
