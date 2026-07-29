from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("approve_vendor", "Approve Vendor"),
                    ("reject_vendor", "Reject Vendor"),
                    ("suspend_vendor", "Suspend Vendor"),
                    ("ban_user", "Ban User"),
                    ("suspend_user", "Suspend User"),
                    ("reinstate_user", "Reinstate User"),
                    ("delete_content", "Delete Content"),
                    ("flag_resolve", "Flag Resolve"),
                    ("approve_package", "Approve Package"),
                    ("reject_package", "Reject Package"),
                    ("hard_delete_package", "Hard Delete Package"),
                ],
                max_length=30,
            ),
        ),
    ]
