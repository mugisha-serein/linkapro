import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('linkapro')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Beat schedule configuration
app.conf.beat_schedule = {
    'check-redis-health': {
        'task': 'apps.accounts.tasks.check_redis_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-login-activities': {
        'task': 'apps.accounts.tasks.cleanup_old_login_activities',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')