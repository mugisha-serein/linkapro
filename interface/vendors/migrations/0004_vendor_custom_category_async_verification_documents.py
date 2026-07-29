from django.db import migrations, models


def backfill_document_metadata(apps, schema_editor):
    VerificationDocument = apps.get_model("vendors", "VerificationDocument")
    VerificationDocument.objects.filter(secure_url__isnull=False).exclude(secure_url="").update(
        cloudinary_secure_url=models.F("secure_url"),
        upload_status="completed",
        verification_status="pending_review",
        fraud_status="review_required",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0003_portfolioimage_async_upload"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorprofile",
            name="custom_category",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AlterField(
            model_name="verificationdocument",
            name="secure_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="mime_type",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="file_size",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="cloudinary_public_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="cloudinary_secure_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="upload_status",
            field=models.CharField(
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
        migrations.AddField(
            model_name="verificationdocument",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("pending_review", "Pending Review"),
                    ("verified", "Verified"),
                    ("rejected", "Rejected"),
                    ("failed", "Failed"),
                ],
                default="pending_review",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="failure_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="temp_upload_path",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(backfill_document_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="verificationdocument",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
