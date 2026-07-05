from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("vendors", "0006_servicepackage_soft_delete_approval_tier"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfolioimage",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="%(class)s_deleted",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="media_type",
            field=models.CharField(choices=[("image", "Image"), ("video", "Video")], default="image", max_length=10),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="quality_status",
            field=models.CharField(
                choices=[
                    ("pending_analysis", "Pending Analysis"),
                    ("passed", "Passed"),
                    ("failed", "Failed"),
                    ("needs_manual_review", "Needs Manual Review"),
                ],
                default="passed",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="visibility_status",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("waiting_approval", "Waiting Approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="approved",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="failure_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="mime_type",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="file_size",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="local_preview_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="cloudinary_public_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="cloudinary_secure_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="width",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="height",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="duration_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="analyzer_score",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="analyzer_summary",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name="portfolioimage",
            name="upload_status",
            field=models.CharField(
                choices=[
                    ("staged", "Staged"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("uploaded", "Uploaded"),
                    ("processing_deferred", "Processing Deferred"),
                    ("failed", "Failed"),
                ],
                default="uploaded",
                max_length=30,
            ),
        ),
    ]
