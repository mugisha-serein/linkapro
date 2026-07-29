# Django Settings Module
# 
# Settings are controlled via the DJANGO_SETTINGS_MODULE environment variable.
# If not set, Django defaults to 'django.conf' but the Celery app and manage.py
# will use the explicitly configured module.
#
# Environment-specific modules:
# - interface.settings.development: For local development
# - interface.settings.production: For production deployment
# - interface.settings.test: For unit/integration testing
#
# The settings are selected via DJANGO_SETTINGS_MODULE environment variable,
# which is set in:
# - Celery: tasks/celery.py (local fallback only; production must set it)
# - Docker Compose: docker-compose.yml
# - Render: Environment variable in dashboard (must be production)
# - pytest: pytest.ini (should be test)
#
# This __init__.py is imported by Django's configuration system.
# Avoid placing initialization code here; use environment variables instead.

from .base import *
