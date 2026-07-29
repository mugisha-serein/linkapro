import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0011_encrypt_totp_secret"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordHistoryEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("password_hash", models.TextField()),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_history_entries",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="passwordhistoryentry",
            index=models.Index(fields=["user", "-created_at"], name="id_pwd_hist_user_created_idx"),
        ),
    ]
