from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0014_vendordomaineventoutbox_vendoridempotencyrecord_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InquiryAbuseRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("requester_identity", models.UUIDField(db_index=True)),
                ("payload_digest", models.CharField(max_length=64)),
                ("duplicate_window_key", models.BigIntegerField()),
                (
                    "created_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inquiry_abuse_records",
                        to="vendors.vendorprofile",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["requester_identity", "vendor", "created_at"],
                        name="vendors_inquiry_abuse_rate_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "requester_identity",
                            "vendor",
                            "payload_digest",
                            "duplicate_window_key",
                        ),
                        name="vendors_inquiry_abuse_duplicate_window_unique",
                    ),
                ],
            },
        ),
    ]
