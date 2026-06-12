# Generated manually after audit confirmed missing governance migrations.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("identity", "0003_user_totp_secret_user_two_factor_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformMetric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(unique=True)),
                ("total_users", models.PositiveIntegerField(default=0)),
                ("total_planners", models.PositiveIntegerField(default=0)),
                ("total_vendors", models.PositiveIntegerField(default=0)),
                ("active_vendors", models.PositiveIntegerField(default=0)),
                ("pending_vendor_approvals", models.PositiveIntegerField(default=0)),
                ("total_events", models.PositiveIntegerField(default=0)),
                ("total_inquiries", models.PositiveIntegerField(default=0)),
                ("total_reviews", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("approve_vendor", "Approve Vendor"),
                            ("reject_vendor", "Reject Vendor"),
                            ("suspend_vendor", "Suspend Vendor"),
                            ("ban_user", "Ban User"),
                            ("suspend_user", "Suspend User"),
                            ("reinstate_user", "Reinstate User"),
                            ("delete_content", "Delete Content"),
                            ("flag_resolve", "Flag Resolve"),
                        ],
                        max_length=30,
                    ),
                ),
                ("target_type", models.CharField(max_length=50)),
                ("target_id", models.UUIDField()),
                ("details", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "admin",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admin_actions",
                        to="identity.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContentFlag",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                (
                    "content_type",
                    models.CharField(
                        choices=[
                            ("vendor_profile", "Vendor Profile"),
                            ("review", "Review"),
                            ("portfolio_image", "Portfolio Image"),
                        ],
                        max_length=30,
                    ),
                ),
                ("content_id", models.UUIDField()),
                ("reason", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("reviewed", "Reviewed"),
                            ("dismissed", "Dismissed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("admin_notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reported_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flags_reported",
                        to="identity.user",
                    ),
                ),
            ],
        ),
    ]
