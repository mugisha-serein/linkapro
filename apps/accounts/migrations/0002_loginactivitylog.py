# Generated migration for LoginActivityLog model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),  # Adjust this to your latest migration
    ]

    operations = [
        migrations.CreateModel(
            name='LoginActivityLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ip_address', models.GenericIPAddressField()),
                ('country_code', models.CharField(blank=True, max_length=2, null=True)),
                ('device_fingerprint', models.CharField(blank=True, max_length=64, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='loginactivitylog',
            index=models.Index(fields=['user', '-timestamp'], name='accounts_lo_user_id_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='loginactivitylog',
            index=models.Index(fields=['ip_address', '-timestamp'], name='accounts_lo_ip_address_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='loginactivitylog',
            index=models.Index(fields=['country_code', '-timestamp'], name='accounts_lo_country_code_timestamp_idx'),
        ),
    ]
