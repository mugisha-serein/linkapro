from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .base import _csv_env

DEBUG = False
ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set.")

if not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured("DATABASE_URL must be set.")

DATABASES["default"] = dj_database_url.config(
    conn_max_age=600,
    ssl_require=True
)

CORS_ALLOWED_ORIGINS = _csv_env("CORS_ALLOWED_ORIGINS")
if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be set.")

CSRF_TRUSTED_ORIGINS = _csv_env("CSRF_TRUSTED_ORIGINS") or CORS_ALLOWED_ORIGINS

# Celery settings
CELERY_BROKER_URL = os.environ.get('REDIS_URL')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# caching settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL'),
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
