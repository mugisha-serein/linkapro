from .base import *
from .base import _csv_env
from django_app.common.redis_config import redis_ssl_options, redis_uses_tls

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Database Configuration for Local Development
# Uses DATABASE_URL when present. Falls back to DB_* only when all required
# values are provided. Otherwise base.py uses local SQLite for a no-friction boot.
if not os.environ.get("DATABASE_URL") and all(
    os.environ.get(name) for name in ["DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST"]
):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
    }

# Redis Configuration for Local Development
# Override with localhost Redis (production may use managed Redis)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery Configuration for Local Development
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
if redis_uses_tls(REDIS_URL):
    CELERY_BROKER_USE_SSL = redis_ssl_options(REDIS_URL)
    CELERY_REDIS_BACKEND_USE_SSL = redis_ssl_options(REDIS_URL)

# CORS Configuration for Local Development
# Allow requests from localhost frontend
CORS_ALLOWED_ORIGINS = _csv_env(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)

# CSRF Configuration for Local Development
# Allow CSRF from localhost frontend
CSRF_TRUSTED_ORIGINS = _csv_env(
    "CSRF_TRUSTED_ORIGINS",
    ",".join(CORS_ALLOWED_ORIGINS),
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
FASTAPI_INTERNAL_URL = os.environ.get("FASTAPI_INTERNAL_URL", "http://localhost:8001")
TOKEN_ENV = os.environ.get("TOKEN_ENV", "development")

# Cache Configuration for Local Development
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        **({"OPTIONS": redis_ssl_options(REDIS_URL)} if redis_uses_tls(REDIS_URL) else {}),
    }
}
