from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0017_rename_vendors_profile_view_logged_idx_vendorsprofileviewlogged_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="inquiry",
            name="requester_user_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
