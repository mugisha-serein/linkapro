import os
from celery import Celery
import django
from django.apps import apps

PRODUCTION_SETTINGS_ERROR = "DJANGO_SETTINGS_MODULE must be set for Celery worker/beat in production."
LOCAL_SETTINGS_MODULE = "django_app.settings.development"


def resolve_celery_settings_module(environ=os.environ) -> str:
    configured = (environ.get("DJANGO_SETTINGS_MODULE") or "").strip()
    if configured:
        return configured

    if _is_production_like_environment(environ):
        raise RuntimeError(PRODUCTION_SETTINGS_ERROR)

    return LOCAL_SETTINGS_MODULE


def _is_production_like_environment(environ) -> bool:
    return (
        _is_truthy(environ.get("RENDER"))
        or bool((environ.get("RENDER_EXTERNAL_HOSTNAME") or "").strip())
        or bool((environ.get("RENDER_SERVICE_ID") or "").strip())
        or _is_production_value(environ.get("FASTAPI_ENV"))
        or _is_production_value(environ.get("DJANGO_ENV"))
        or _is_production_value(environ.get("ENVIRONMENT"))
        or _is_false(environ.get("DEBUG"))
        or _is_false(environ.get("DJANGO_DEBUG"))
    )


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_production_value(value: str | None) -> bool:
    return (value or "").strip().lower() in {"prod", "production"}


def _is_false(value: str | None) -> bool:
    return (value or "").strip().lower() in {"0", "false", "no", "off"}


os.environ["DJANGO_SETTINGS_MODULE"] = resolve_celery_settings_module()

app = Celery('linkapro')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# These task modules live in the root tasks package, not inside installed
# Django apps, so Celery autodiscovery will not import them by itself.
app.conf.imports = tuple(set(app.conf.imports or ()) | {
    "tasks.document_tasks",
    "tasks.email_tasks",
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
