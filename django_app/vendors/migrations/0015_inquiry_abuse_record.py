from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0014_vendordomaineventoutbox_vendoridempotencyrecord_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="InquiryAbuseRecord",
            fields=[
                ("