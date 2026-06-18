from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("vendors", "0005_verification_document_deferred_odcr"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicepackage",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("waiting_approval", "Waiting Approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="waiting_approval",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="package_tier",
            field=models.CharField(
                choices=[
                    ("standard", "Standard"),
                    ("premier", "Premier"),
                    ("gold", "Gold"),
                ],
                default="standard",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_deleted",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
