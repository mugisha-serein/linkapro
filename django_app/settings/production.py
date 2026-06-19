from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .base import _csv_env
from django_app.common.redis_config import redis_ssl_options, redis_uses_tls, validate_redis_url

DEBUG = False
ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")
render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)
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

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "").strip()
if not SENDGRID_API_KEY:
    raise ImproperlyConfigured("SENDGRID_API_KEY must be set for production password reset emails.")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "").strip()
if not DEFAULT_FROM_EMAIL:
    raise ImproperlyConfigured("DEFAULT_FROM_EMAIL must be set for production emails.")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip()
if not FRONTEND_URL:
    raise ImproperlyConfigured("FRONTEND_URL must be set for password reset links.")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

REDIS_URL = validate_redis_url(REDIS_URL, required=True)

# Celery settings
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# caching settings
_redis_cache_options = redis_ssl_options(REDIS_URL) if redis_uses_tls(REDIS_URL) else {}
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        **({"OPTIONS": _redis_cache_options} if _redis_cache_options else {}),
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
