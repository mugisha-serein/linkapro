import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0015_inquiry_abuse_record"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorProfileViewed",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("view_date", models.DateField()),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile_view_counts",
                        to="vendors.vendorprofile",
                    ),
                ),
            ],
            options={
                "db_table": "vendors_profile_view_logged",
                "indexes": [
                    models.Index(
                        fields=["vendor", "view_date"],
                        name="vendors_profile_view_logged_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("vendor", "view_date"),
                        name="vendors_profile_view_logged_vendor_date_unique",
                    ),
                ],
            },
        ),
    ]
