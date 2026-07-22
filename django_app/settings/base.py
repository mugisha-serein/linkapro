import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
import structlog
import dj_database_url

from django_app.common.redis_config import get_redis_url, redis_ssl_options, redis_uses_tls

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _csv_env(name: str, default: str = "") -> list[str]:
    raw_value = os.environ.get(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if settings_module.endswith((".development", ".test")):
        SECRET_KEY = "insecure-local-development-secret-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")

ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    
    # Rest Framework
    "rest_framework",
    "rest_framework_simplejwt",
    
    # Apps
    "django_app.identity",
    "django_app.events",
    "django_app.vendors",
    "django_app.documents.apps.DocumentsConfig",
    "django_app.governance.apps.GovernanceConfig",
    "django_app.payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "payments.infrastructure.middleware.HmacRequestValidator",
    "payments.infrastructure.correlation_middleware.CorrelationMiddleware"
]

ROOT_URLCONF = "django_app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "django_app.wsgi.application"

# Database
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.environ.get("DB_NAME"),
#         "USER": os.environ.get("DB_USER"),
#         "PASSWORD": os.environ.get("DB_PASSWORD"),
#         "HOST": os.environ.get("DB_HOST"),
#         "PORT": os.environ.get("DB_PORT"),
#         'OPTIONS': {},
#     }
# }

DJANGO_DATABASE_SCHEMES = {
    "cockroach",
    "mssql",
    "mssqlms",
    "mysql",
    "mysql-connector",
    "mysql2",
    "mysqlgis",
    "oracle",
    "oraclegis",
    "pgsql",
    "postgis",
    "postgres",
    "postgresql",
    "redshift",
    "spatialite",
    "sqlite",
    "timescale",
    "timescalegis",
}


def _mask_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    if not parsed.netloc:
        return database_url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    user = f"{parsed.username}:***@" if parsed.username else ""
    return parsed._replace(netloc=f"{user}{host}{port}").geturl()


def _django_database_url() -> str:
    explicit = os.getenv("DJANGO_DATABASE_URL")
    if explicit:
        return explicit
    fallback = os.getenv("DATABASE_URL")
    if not fallback:
        return f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    scheme = urlparse(fallback).scheme
    if scheme not in DJANGO_DATABASE_SCHEMES:
        masked = _mask_database_url(fallback)
        raise ImproperlyConfigured(
            "DATABASE_URL is not compatible with Django. Set DJANGO_DATABASE_URL "
            f"for Django and FASTAPI_DATABASE_URL for FastAPI. Received {masked!r}."
        )
    return fallback


DATABASES = {"default": dj_database_url.parse(_django_database_url())}

if os.environ.get('DATABASE_SSL', 'false').lower() == 'true':
    DATABASES['default']['OPTIONS']['sslmode'] = 'verify-full'
    DATABASES['default']['OPTIONS']['sslcert'] = '/etc/ssl/certs/client-cert.pem'
    DATABASES['default']['OPTIONS']['sslkey'] = '/etc/ssl/private/client-key.pem'
    DATABASES['default']['OPTIONS']['sslrootcert'] = '/etc/ssl/certs/ca.pem'

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE = int(os.environ.get("VENDOR_PORTFOLIO_MAX_UPLOAD_SIZE", 4 * 1024 * 1024))
VENDOR_PORTFOLIO_MIN_IMAGE_WIDTH = int(os.environ.get("VENDOR_PORTFOLIO_MIN_IMAGE_WIDTH", 800))
VENDOR_PORTFOLIO_MIN_IMAGE_HEIGHT = int(os.environ.get("VENDOR_PORTFOLIO_MIN_IMAGE_HEIGHT", 600))
VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB = int(os.environ.get("VENDOR_VERIFICATION_DOCUMENT_MAX_SIZE_MB", 5))
ODCR_ENABLED = os.environ.get("ODCR_ENABLED", "false").lower() == "true"
ODCR_API_URL = os.environ.get("ODCR_API_URL", "")
ODCR_API_KEY = os.environ.get("ODCR_API_KEY", "")
ODCR_TIMEOUT_SECONDS = int(os.environ.get("ODCR_TIMEOUT_SECONDS", 10))
MEDIA_ANALYZER_ENABLED = os.environ.get("MEDIA_ANALYZER_ENABLED", "false").lower() == "true"
MEDIA_ANALYZER_API_URL = os.environ.get("MEDIA_ANALYZER_API_URL", "")
MEDIA_ANALYZER_API_KEY = os.environ.get("MEDIA_ANALYZER_API_KEY", "")
MEDIA_ANALYZER_TIMEOUT_SECONDS = int(os.environ.get("MEDIA_ANALYZER_TIMEOUT_SECONDS", 10))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "payments.infrastructure.authentication.HardenedJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "forgot_password_ip": os.environ.get("FORGOT_PASSWORD_IP_RATE", "5/min"),
        "forgot_password_email": os.environ.get("FORGOT_PASSWORD_EMAIL_RATE", "3/hour"),
        "reset_password_ip": os.environ.get("RESET_PASSWORD_IP_RATE", "10/min"),
        "reset_password_token": os.environ.get("RESET_PASSWORD_TOKEN_RATE", "5/hour"),
        "login_ip": os.environ.get("LOGIN_IP_RATE", "10/min"),
        "login_email": os.environ.get("LOGIN_EMAIL_RATE", "5/min"),
        "login_user": os.environ.get("LOGIN_USER_RATE", "20/hour"),
        "register_ip": os.environ.get("REGISTER_IP_RATE", "5/hour"),
        "register_email_domain": os.environ.get("REGISTER_EMAIL_DOMAIN_RATE", "20/hour"),
        "two_factor_ip": os.environ.get("TWO_FACTOR_IP_RATE", "10/min"),
        "two_factor_temp_token": os.environ.get("TWO_FACTOR_TEMP_TOKEN_RATE", "5/min"),
        "google_oauth_ip": os.environ.get("GOOGLE_OAUTH_IP_RATE", "20/min"),
        "public_vendor_inquiry": os.environ.get("PUBLIC_VENDOR_INQUIRY_RATE", "5/hour"),
    },
}

RATE_LIMIT_HASH_KEY = os.environ.get("RATE_LIMIT_HASH_KEY", "")
LOGIN_FAILURE_LOCKOUT_THRESHOLD = int(os.environ.get("LOGIN_FAILURE_LOCKOUT_THRESHOLD", "8"))
LOGIN_FAILURE_LOCKOUT_SECONDS = int(os.environ.get("LOGIN_FAILURE_LOCKOUT_SECONDS", "900"))
MFA_FAILURE_LOCKOUT_THRESHOLD = int(os.environ.get("MFA_FAILURE_LOCKOUT_THRESHOLD", "5"))
MFA_FAILURE_LOCKOUT_SECONDS = int(os.environ.get("MFA_FAILURE_LOCKOUT_SECONDS", "900"))
PASSWORD_RECOVERY_TRUST_X_FORWARDED_FOR = (
    os.environ.get("PASSWORD_RECOVERY_TRUST_X_FORWARDED_FOR", "false").lower() == "true"
)

AUTH_USER_MODEL = "identity.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    'UPDATE_LAST_LOGIN': True,
    "ALGORITHM": "HS256",
    'AUDIENCE': None,
    'ISSUER': None,
    "SIGNING_KEY": SECRET_KEY,
    'JTI_CLAIM': 'jti',
    "AUTH_HEADER_TYPES": ("Bearer",),
}

JWE_PRIVATE_KEY = os.environ.get("JWE_PRIVATE_KEY", "")

PASSWORD_RESET_TIMEOUT = timedelta(hours=1)
EMAIL_VERIFICATION_TIMEOUT = timedelta(days=3)


def _default_token_env() -> str:
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "").lower()
    if settings_module.endswith(".test"):
        return "test"
    if settings_module.endswith(".development"):
        return "development"
    return "development" if DEBUG else "production"


TOKEN_ENV = os.environ.get(
    "TOKEN_ENV",
    os.environ.get("APP_ENV", os.environ.get("DJANGO_ENV", _default_token_env())),
)
ACCEPT_LEGACY_PAYMENT_ENV_TOKENS = (
    os.environ.get("ACCEPT_LEGACY_PAYMENT_ENV_TOKENS", "true").lower() == "true"
)

# Celery
REDIS_URL = get_redis_url()
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
MARKETPLACE_PROJECTION_OUTBOX_RETRY_BATCH_SIZE = int(
    os.environ.get("MARKETPLACE_PROJECTION_OUTBOX_RETRY_BATCH_SIZE", "25")
)
if redis_uses_tls(REDIS_URL):
    CELERY_BROKER_USE_SSL = redis_ssl_options(REDIS_URL)
    CELERY_REDIS_BACKEND_USE_SSL = redis_ssl_options(REDIS_URL)

CELERY_BEAT_SCHEDULE = {
    "expire-stale-payments": {
        "task": "payments.tasks.expire_stale_payments_task",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "retry-marketplace-projection-outbox": {
        "task": "tasks.marketplace_sync.retry_due_marketplace_projection_outbox_events_task",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "reconcile-marketplace-projection": {
        "task": "tasks.marketplace_sync.reconcile_marketplace_projection_task",
        "schedule": crontab(hour=3, minute=0),  # Daily
    },
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processor': structlog.processors.JSONRenderer(),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# CORS
CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "False").lower() == "true"
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = _csv_env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = _csv_env("CSRF_TRUSTED_ORIGINS")

# Cloudinary
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

# SendGrid
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@linkapro.local")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", SENDGRID_API_KEY)

# Google OAuth
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL")

# reCAPTCHA
RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "")

# FastAPI internal URL (for Celery tasks)
FASTAPI_INTERNAL_URL = os.environ.get("FASTAPI_INTERNAL_URL")
FASTAPI_INTERNAL_SHARED_SECRET = os.environ.get("FASTAPI_INTERNAL_SHARED_SECRET")

# Flutterwave
FLW_SECRET_KEY = os.environ.get("FLW_SECRET_KEY", "")
FLW_SECRET_HASH = os.environ.get("FLW_SECRET_HASH", "")
PAYMENT_ENV = os.environ.get("PAYMENT_ENV", "test")

# HashiCorp Vault
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID", "")
VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID", "")
VAULT_TRANSIT_KEY_NAME = os.environ.get("VAULT_TRANSIT_KEY_NAME", "linkapro-payments-kek")

# HMAC Key
PROVIDER_REFERENCE_HMAC_KEY = os.environ.get("PROVIDER_REFERENCE_HMAC_KEY")

# Flutterwave Webhook Decryptor
FLW_ENCRYPTION_KEY = os.environ.get("FLW_ENCRYPTION_KEY", "")
