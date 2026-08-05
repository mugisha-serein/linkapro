from decimal import Decimal

from django.db import migrations, models


def normalize_event_total_budget(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    for event in Event.objects.only("id", "total_budget").iterator():
        if event.total_budget is not None:
            event.total_budget = Decimal(str(event.total_budget))
            event.save(update_fields=["total_budget"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0004_normalize_budgetline_decimal_amounts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="total_budget",
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=12),
        ),
        migrations.RunPython(normalize_event_total_budget, migrations.RunPython.noop),
    ]
