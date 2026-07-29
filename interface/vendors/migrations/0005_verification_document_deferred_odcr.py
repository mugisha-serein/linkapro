from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0004_vendor_custom_category_async_verification_documents"),
    ]

    operations = [
        migrations.AlterField(
            model_name="verificationdocument",
            name="upload_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("processing_deferred", "Processing Deferred"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="verificationdocument",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("pending_review", "Pending Review"),
                    ("needs_manual_review", "Needs Manual Review"),
                    ("verified", "Verified"),
                    ("rejected", "Rejected"),
                    ("failed", "Failed"),
                ],
                default="pending_review",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="odcr_status",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="odcr_score",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="verificationdocument",
            name="odcr_result_summary",
            field=models.TextField(blank=True, null=True),
        ),
    ]
