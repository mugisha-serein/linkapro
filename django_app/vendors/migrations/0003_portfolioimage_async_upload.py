from django.db import migrations, models


def backfill_completed_uploads(apps, schema_editor):
    PortfolioImage = apps.get_model("vendors", "PortfolioImage")
    PortfolioImage.objects.filter(secure_url__isnull=False).exclude(secure_url="").update(
        upload_status="completed",
        upload_error=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0002_verificationdocument"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portfolioimage",
            name="public_id",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name="portfolioimage",
            name="secure_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="upload_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("processing", "Processing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="completed",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="upload_error",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="original_filename",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="portfolioimage",
            name="temp_upload_path",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.RunPython(backfill_completed_uploads, migrations.RunPython.noop),
    ]
