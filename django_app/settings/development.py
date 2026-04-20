from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Override for local development
DATABASES["default"]["HOST"] = os.environ.get("DB_HOST", "localhost")