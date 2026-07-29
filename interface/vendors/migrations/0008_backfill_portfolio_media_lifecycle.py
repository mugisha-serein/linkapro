from django.db import migrations, models
from django.db.models import Case, Q, Value, When
from django.utils import timezone


def backfill_portfolio_media(apps, schema_editor):
    PortfolioImage = apps.get_model("vendors", "PortfolioImage")
    has_cloud_url = (
        Q(cloudinary_secure_url__isnull=False)
        & ~Q(cloudinary_secure_url="")
    ) | (
        Q(secure_url__isnull=False)
        & ~Q(secure_url="")
    )

    PortfolioImage.objects.update(
        is_deleted=False,
        is_active=True,
        media_type="image",
        cloudinary_public_id=Case(
            When(Q(cloudinary_public_id__isnull=True) | Q(cloudinary_public_id=""), then=models.F("public_id")),
            default=models.F("cloudinary_public_id"),
        ),
        cloudinary_secure_url=Case(
            When(Q(cloudinary_secure_url__isnull=True) | Q(cloudinary_secure_url=""), then=models.F("secure_url")),
            default=models.F("cloudinary_secure_url"),
        ),
        upload_status=Case(
            When(has_cloud_url, then=Value("uploaded")),
            When(upload_status="completed", then=Value("uploaded")),
            When(upload_status="pending", then=Value("queued")),
            default=models.F("upload_status"),
        ),
        quality_status=Case(
            When(has_cloud_url | Q(upload_status="completed"), then=Value("passed")),
            default=Value("needs_manual_review"),
        ),
        visibility_status=Case(
            When(has_cloud_url | Q(upload_status="completed"), then=Value("approved")),
            default=Value("waiting_approval"),
        ),
        updated_at=timezone.now(),
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("vendors", "0007_portfolio_media_lifecycle"),
    ]

    operations = [
        migrations.RunPython(backfill_portfolio_media, migrations.RunPython.noop),
    ]
