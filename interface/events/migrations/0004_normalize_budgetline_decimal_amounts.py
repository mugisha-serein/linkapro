from decimal import Decimal

from django.db import migrations, models


def normalize_budgetline_amounts(apps, schema_editor):
    BudgetLine = apps.get_model("events", "BudgetLine")
    for line in BudgetLine.objects.only("id", "estimated_cost", "actual_cost").iterator():
        update_fields = []
        if line.estimated_cost is not None:
            line.estimated_cost = Decimal(str(line.estimated_cost))
            update_fields.append("estimated_cost")
        if line.actual_cost is not None:
            line.actual_cost = Decimal(str(line.actual_cost))
            update_fields.append("actual_cost")
        if update_fields:
            line.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0003_eventstagetemplate_event_country_eventstage_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="budgetline",
            name="estimated_cost",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name="budgetline",
            name="actual_cost",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(normalize_budgetline_amounts, migrations.RunPython.noop),
    ]
