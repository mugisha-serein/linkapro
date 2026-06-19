from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0008_backfill_portfolio_media_lifecycle"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portfolioimage",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
