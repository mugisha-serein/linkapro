import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0001_initial"),
        ("vendors", "0002_verificationdocument"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventVendorAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("shortlisted", "Shortlisted"),
                            ("contacted", "Contacted"),
                            ("booked", "Booked"),
                            ("rejected", "Rejected"),
                        ],
                        default="shortlisted",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vendor_assignments",
                        to="events.event",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_assignments",
                        to="vendors.vendorprofile",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="eventvendorassignment",
            constraint=models.UniqueConstraint(fields=("event", "vendor"), name="unique_event_vendor_assignment"),
        ),
        migrations.AddIndex(
            model_name="eventvendorassignment",
            index=models.Index(fields=["event", "status"], name="events_even_event_i_3afb62_idx"),
        ),
        migrations.AddIndex(
            model_name="eventvendorassignment",
            index=models.Index(fields=["vendor"], name="events_even_vendor__4946e4_idx"),
        ),
    ]
