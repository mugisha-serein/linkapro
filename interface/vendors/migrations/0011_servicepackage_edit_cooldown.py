from datetime import timedelta

from django.db import migrations, models


COOLDOWN_DAYS = 15


def backfill_package_cooldown(apps, schema_editor):
    ServicePackage = apps.get_model("vendors", "ServicePackage")
    for package in ServicePackage.objects.filter(approval_status="approved"):
        approved_at = package.updated_at
        package.last_approved_at = approved_at
        package.next_vendor_edit_allowed_at = approved_at + timedelta(days=COOLDOWN_DAYS)
        package.save(update_fields=["last_approved_at", "next_vendor_edit_allowed_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0010_clear_portfolio_local_preview_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicepackage",
            name="last_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="last_vendor_public_edit_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="servicepackage",
            name="next_vendor_edit_allowed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_package_cooldown, migrations.RunPython.noop),
    ]
