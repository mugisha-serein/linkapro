from django.db import migrations


def clear_private_portfolio_preview_urls(apps, schema_editor):
    PortfolioImage = apps.get_model("vendors", "PortfolioImage")
    PortfolioImage.objects.filter(local_preview_url__icontains="vendor_portfolio_uploads").update(
        local_preview_url=None,
    )
    PortfolioImage.objects.filter(local_preview_url__startswith="/media/").update(
        local_preview_url=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0009_portfolio_media_lifecycle_constraints"),
    ]

    operations = [
        migrations.RunPython(clear_private_portfolio_preview_urls, migrations.RunPython.noop),
    ]
