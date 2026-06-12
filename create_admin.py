# create_admin.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings.production")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser(
        username="linkapro",
        email="linkapro@support.com",
        password="Linkapro@123",
    )
    print("Admin created")
else:
    print("Admin already exists")