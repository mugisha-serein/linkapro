import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module:
    raise RuntimeError("DJANGO_SETTINGS_MODULE must be set explicitly for Celery.")
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

app = Celery('linkapro')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# payments is a standalone package, so register it explicitly.
app.autodiscover_tasks(['payments'])
