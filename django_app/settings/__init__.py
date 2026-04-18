# Default to development settings; override via DJANGO_SETTINGS_MODULE
try:
    from .base import *
except ImportError:
    from .development import *