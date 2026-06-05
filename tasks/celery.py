import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# Use development as default; production is set via DJANGO_SETTINGS_MODULE env var
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_app.settings.development')

app = Celery('linkapro')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
# payments is a standalone package, so register it explicitly.
app.autodiscover_tasks(['payments'])
