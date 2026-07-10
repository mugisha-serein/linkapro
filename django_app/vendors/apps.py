from django.apps import AppConfig


class VendorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app.vendors"
    label = "vendors"

    def ready(self) -> None:
        # Register vendor models that live outside models.py without importing
        # infrastructure or application composition during app loading.
        from . import abuse_models  # noqa: F401
