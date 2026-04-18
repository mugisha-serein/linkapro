from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Override database for local dev if needed
DATABASES["default"]["HOST"] = "localhost"