import os
from celery import Celery
import django
from django.apps import apps

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings.development")

app = Celery('linkapro')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# These task modules live in the root tasks package, not inside installed
# Django apps, so Celery autodiscovery will not import them by itself.
app.conf.imports = tuple(set(app.conf.imports or ()) | {
    "tasks.document_tasks",
    "tasks.image_tasks",
    "payments.tasks",
})

if not apps.ready and not getattr(apps, "loading", False):
    django.setup()

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# payments is a standalone package, so register it explicitly.
app.autodiscover_tasks(['payments'])
if apps.ready:
    app.loader.import_default_modules()
