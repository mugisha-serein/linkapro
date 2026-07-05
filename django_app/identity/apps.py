from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app.identity"
    label = "identity"

    def ready(self):
        import django_app.identity.receivers  # noqa: F401
