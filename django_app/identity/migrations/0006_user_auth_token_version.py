# Generated manually for identity session-version enforcement

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0005_passwordresettoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="auth_token_version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
