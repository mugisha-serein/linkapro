from .base import *
from .base import _csv_env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Database Configuration for Local Development
# Ensure localhost is the default host for development database
DATABASES["default"]["HOST"] = os.environ.get("DB_HOST")
DATABASES["default"]["PORT"] = os.environ.get("DB_PORT")
DATABASES["default"]["NAME"] = os.environ.get("DB_NAME")
DATABASES["default"]["USER"] = os.environ.get("DB_USER")
DATABASES["default"]["PASSWORD"] = os.environ.get("DB_PASSWORD")

# Redis Configuration for Local Development
# Override with localhost Redis (production may use managed Redis)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery Configuration for Local Development
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

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

# Cache Configuration for Local Development
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}