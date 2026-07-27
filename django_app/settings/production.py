import os

from .base import *
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .base import _csv_env
from django_app.common.redis_config import redis_ssl_options, redis_uses_tls, validate_redis_url

DEBUG = False
PASSWORD_RECOVERY_TRUST_X_FORWARDED_FOR = (
    os.environ.get("PASSWORD_RECOVERY_TRUST_X_FORWARDED_FOR", "true").lower() == "true"
)
ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")
render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set.")

django_database_url = (
    os.environ.get("DJANGO_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or ""
).strip()
if not django_database_url:
    raise ImproperlyConfigured("DJANGO_DATABASE_URL must be set.")
if django_database_url.startswith(("postgresql+asyncpg://", "postgres+asyncpg://")):
    raise ImproperlyConfigured(
        "DJANGO_DATABASE_URL must use a Django-compatible PostgreSQL scheme "
        "such as postgresql:// or postgres://, not asyncpg."
    )

DATABASES["default"] = dj_database_url.parse(
    django_database_url,
    conn_max_age=600,
    ssl_require=True,
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

TOKEN_ENV = os.environ.get("TOKEN_ENV", "production").strip()
if not TOKEN_ENV:
    raise ImproperlyConfigured("TOKEN_ENV must be set for production identity tokens.")

if not PASSWORD_RESET_HASH_KEY:
    raise ImproperlyConfigured("PASSWORD_RESET_HASH_KEY must be set")

def _vault_setting(name: str) -> str:
    return str(globals().get(name, "") or "").strip()


def _vault_file_setting(name: str) -> str:
    file_name = f"{name}_FILE"
    path = _vault_setting(file_name)
    if not path:
        return _vault_setting(name)
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ImproperlyConfigured(f"{file_name} could not be read for production field encryption.") from exc
    if not value:
        raise ImproperlyConfigured(f"{file_name} must not be blank for production field encryption.")
    return value


_vault_addr = _vault_setting("VAULT_ADDR")
if not _vault_addr:
    raise ImproperlyConfigured(
        "VAULT_ADDR must be set for production field encryption."
    )
_vault_url = urlparse(_vault_addr)
if _vault_url.scheme not in {"https"} or not _vault_url.netloc:
    raise ImproperlyConfigured("VAULT_ADDR must be a valid HTTPS URL for production field encryption.")
if _vault_url.params or _vault_url.query or _vault_url.fragment:
    raise ImproperlyConfigured("VAULT_ADDR must not include params, query, or fragment.")
if not _vault_setting("VAULT_TRANSIT_KEY_NAME"):
    raise ImproperlyConfigured("VAULT_TRANSIT_KEY_NAME must be set for production field encryption.")
if not _vault_file_setting("VAULT_ROLE_ID"):
    raise ImproperlyConfigured("VAULT_ROLE_ID or VAULT_ROLE_ID_FILE must be set for production field encryption.")
if not _vault_file_setting("VAULT_SECRET_ID"):
    raise ImproperlyConfigured("VAULT_SECRET_ID or VAULT_SECRET_ID_FILE must be set for production field encryption.")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

try:
    REDIS_URL = os.environ["REDIS_URL"].rstrip("/")
except KeyError as exc:
    raise ImproperlyConfigured("REDIS_URL must start with redis:// or rediss://") from exc
REDIS_URL = validate_redis_url(REDIS_URL, required=True)

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"{REDIS_URL}/0",
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"{REDIS_URL}/1",
)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

globals().pop("CELERY_BROKER_USE_SSL", None)
globals().pop("CELERY_REDIS_BACKEND_USE_SSL", None)
if redis_uses_tls(CELERY_BROKER_URL):
    CELERY_BROKER_USE_SSL = redis_ssl_options(CELERY_BROKER_URL)
if redis_uses_tls(CELERY_RESULT_BACKEND):
    CELERY_REDIS_BACKEND_USE_SSL = redis_ssl_options(CELERY_RESULT_BACKEND)

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
