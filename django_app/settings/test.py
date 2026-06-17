from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable password hashers for speed
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Email backend for testing
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery always eager
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Shorter token lifetimes for tests
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
PASSWORD_RESET_TIMEOUT = timedelta(hours=1)
EMAIL_VERIFICATION_TIMEOUT = timedelta(days=3)

# Celery always eager for tests (tasks run synchronously)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Skip broker connection entirely
CELERY_BROKER_URL = "memory://"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/15")

# HashiCorp Vault
VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://localhost:8200")
VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID", "")
VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID", "")
VAULT_TRANSIT_KEY_NAME = os.environ.get("VAULT_TRANSIT_KEY_NAME", "linkapro-payments-kek")

# HMAC Key
PROVIDER_REFERENCE_HMAC_KEY = os.environ.get("PROVIDER_REFERENCE_HMAC_KEY", "change-me-in-production")

# JWE Tests
JWE_PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIK7gE4hdm0n2hNpqJpY3cZqPcF4q6ZJQ0nGxJ3M3v4hAoGCCqGSM49
AwEHoUQDQgAEE5BQV9qR0fIq2Z3z5Qq3uFsqZbJ1PjzjV0k2eKj2tZcC5Rj3kC1
... (a valid P-256 private key in PEM format) ...
-----END EC PRIVATE KEY-----"""
